"""Template-mode report authoring.

Instead of building a report from a bare skeleton, start from a full, styled archetype
(an RDL + manifest under templates/library/<name>/), then rebind it: swap the data source
and dataset, and stamp one styled column per field by cloning the template's prototype cells.

This keeps the hard-to-generate styling (fonts, colors, borders, group layout) as known-good
XML authored by Report Builder, while the engine only does mechanical rebinding.
"""

import os
import copy
import json
import uuid
import logging
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional

from .xml_utils import parse_rdl_tree, get_namespace, write_xml
from .columns import _update_tablix_width
from . import report_builder

logger = logging.getLogger(__name__)

_LIBRARY = os.path.join(os.path.dirname(__file__), 'templates', 'library')


def _template_dir(name: str) -> str:
    return os.path.join(_LIBRARY, name)


def list_templates() -> Dict[str, Any]:
    """List available report templates with their manifest metadata."""
    templates = []
    if os.path.isdir(_LIBRARY):
        for name in sorted(os.listdir(_LIBRARY)):
            manifest_path = os.path.join(_template_dir(name), 'manifest.json')
            if os.path.isfile(manifest_path):
                with open(manifest_path, encoding='utf-8') as f:
                    m = json.load(f)
                templates.append({
                    'name': m.get('name', name),
                    'title': m.get('title', name),
                    'description': m.get('description', ''),
                    'category': m.get('category', ''),
                    'supported_sources': m.get('supported_sources', []),
                })
    return {'templates': templates}


def _load_manifest(name: str) -> Optional[Dict[str, Any]]:
    manifest_path = os.path.join(_template_dir(name), 'manifest.json')
    if not os.path.isfile(manifest_path):
        return None
    with open(manifest_path, encoding='utf-8') as f:
        return json.load(f)


def _find_textbox_cell(row: ET.Element, ns: str, textbox_name: str) -> Optional[ET.Element]:
    """Return the TablixCell whose Textbox has the given Name."""
    for cell in row.findall(f'{ns}TablixCells/{ns}TablixCell'):
        tb = cell.find(f'.//{ns}Textbox')
        if tb is not None and tb.get('Name') == textbox_name:
            return cell
    return None


def _stamp_cell(proto_cell: ET.Element, ns: str, textbox_name: str,
                value: str, format_string: Optional[str] = None) -> ET.Element:
    """Deep-copy a prototype cell and set its textbox name, value, and optional format."""
    cell = copy.deepcopy(proto_cell)
    tb = cell.find(f'.//{ns}Textbox')
    tb.set('Name', textbox_name)
    # Keep rd:DefaultName in sync with the textbox Name
    for child in list(tb):
        if child.tag.endswith('}DefaultName'):
            child.text = textbox_name
    text_run = tb.find(f'.//{ns}TextRun')
    val = text_run.find(f'{ns}Value')
    val.text = value
    if format_string:
        style = text_run.find(f'{ns}Style')
        if style is None:
            style = ET.SubElement(text_run, f'{ns}Style')
        fmt = style.find(f'{ns}Format')
        if fmt is None:
            fmt = ET.SubElement(style, f'{ns}Format')
        fmt.text = format_string
    return cell


def _rebind_tablix_columns(root: ET.Element, ns: str, manifest: Dict[str, Any],
                           fields: List[Dict[str, Any]]) -> None:
    """Replace the template's prototype column with one styled column per field."""
    proto = manifest['prototype']
    tablix_name = manifest['tablix_name']
    default_width = proto.get('default_column_width', '1.5in')

    tablix = None
    for tb in root.findall(f'.//{ns}Tablix'):
        if tb.get('Name') == tablix_name:
            tablix = tb
            break
    if tablix is None:
        raise ValueError(f"Template tablix '{tablix_name}' not found")

    rows = tablix.findall(f'.//{ns}TablixBody/{ns}TablixRows/{ns}TablixRow')
    header_row = rows[proto['header_row_index']]
    data_row = rows[proto['data_row_index']]

    header_proto = _find_textbox_cell(header_row, ns, proto['header_textbox'])
    data_proto = _find_textbox_cell(data_row, ns, proto['data_textbox'])
    if header_proto is None or data_proto is None:
        raise ValueError("Template prototype cells not found")

    # Rebuild column definitions
    tablix_columns = tablix.find(f'.//{ns}TablixBody/{ns}TablixColumns')
    for col in list(tablix_columns):
        tablix_columns.remove(col)
    for field in fields:
        col = ET.SubElement(tablix_columns, f'{ns}TablixColumn')
        w = ET.SubElement(col, f'{ns}Width')
        w.text = field.get('width', default_width)

    # Rebuild header + data cells
    header_cells = header_row.find(f'{ns}TablixCells')
    data_cells = data_row.find(f'{ns}TablixCells')
    for cells in (header_cells, data_cells):
        for c in list(cells):
            cells.remove(c)

    for i, field in enumerate(fields):
        name = field['name']
        label = field.get('label', name)
        fmt = field.get('format')
        header_cells.append(_stamp_cell(header_proto, ns, f'Header_{name}_{i}', label))
        data_cells.append(_stamp_cell(data_proto, ns, f'Data_{name}_{i}',
                                      f'=Fields!{name}.Value', fmt))

    # Rebuild column hierarchy: one static member per column
    col_members = tablix.find(f'.//{ns}TablixColumnHierarchy/{ns}TablixMembers')
    for m in list(col_members):
        col_members.remove(m)
    for _ in fields:
        ET.SubElement(col_members, f'{ns}TablixMember')

    _update_tablix_width(tablix, ns)


def create_report_from_template(filepath: str, template: str, title: str, source_type: str,
                                connection: Dict[str, Any], dataset_name: str, query: str,
                                fields: List[Dict[str, Any]],
                                parameters: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Create a report by cloning a styled template and rebinding its data + columns.

    Args mirror create_report, plus `template` (a name from list_templates). Each field may
    include {name, label?, data_field?, type_name?, width?, format?}.
    """
    manifest = _load_manifest(template)
    if manifest is None:
        avail = [t['name'] for t in list_templates()['templates']]
        return {'success': False,
                'message': f"Unknown template '{template}'. Available: {avail}"}
    if source_type not in report_builder._SOURCE_CONFIG:
        return {'success': False,
                'message': f"Unknown source_type '{source_type}'. Use 'fabric' or 'sql'."}
    if not fields:
        return {'success': False, 'message': 'At least one field is required.'}

    parameters = parameters or []
    tree = parse_rdl_tree(os.path.join(_template_dir(template), 'template.rdl'))
    root = tree.getroot()
    ns = get_namespace(root)

    report_id = root.find(f'{report_builder.RD_NS}ReportID')
    if report_id is not None:
        report_id.text = str(uuid.uuid4())

    # Rebind data source: clear and rebuild
    datasource_name = connection.get('name', 'DataSource1')
    connect_string = report_builder._build_connect_string(source_type, connection)
    datasources = root.find(f'{ns}DataSources')
    for ds in list(datasources):
        datasources.remove(ds)
    report_builder._add_datasource(datasources, ns, datasource_name, source_type, connect_string)

    # Rebind dataset: clear and rebuild
    datasets = root.find(f'{ns}DataSets')
    for ds in list(datasets):
        datasets.remove(ds)
    query_parameters = [p['name'] for p in parameters]
    report_builder._add_dataset(datasets, ns, dataset_name, datasource_name, query,
                                fields, query_parameters)

    # Point the tablix at the new dataset, then stamp columns from prototype
    tablix = root.find(f".//{ns}Tablix[@Name='{manifest['tablix_name']}']")
    if tablix is not None:
        dsn = tablix.find(f'{ns}DataSetName')
        if dsn is not None:
            dsn.text = dataset_name
    _rebind_tablix_columns(root, ns, manifest, fields)

    if parameters:
        report_builder._add_report_parameters(root, ns, parameters)

    write_xml(tree, filepath)
    logger.info(f"Created report '{title}' from template '{template}' at {filepath}")
    return {
        'success': True,
        'message': (f"Created report '{title}' from template '{template}' ({source_type}) at "
                    f"{filepath}: dataset '{dataset_name}', {len(fields)} columns, "
                    f"{len(parameters)} parameters"),
        'filepath': filepath,
    }
