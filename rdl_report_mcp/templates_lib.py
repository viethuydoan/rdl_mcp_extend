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


def _find_tablix(root: ET.Element, ns: str, tablix_name: str) -> Optional[ET.Element]:
    for tb in root.findall(f'.//{ns}Tablix'):
        if tb.get('Name') == tablix_name:
            return tb
    return None


def _rebind_table_region(root: ET.Element, ns: str, tablix_name: str,
                         prototype: Dict[str, Any], fields: List[Dict[str, Any]]) -> None:
    """Replace a table tablix's prototype column with one styled column per field."""
    proto = prototype
    default_width = proto.get('default_column_width', '1.5in')

    tablix = _find_tablix(root, ns, tablix_name)
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


def _set_value_text(textbox: ET.Element, ns: str, text: str) -> None:
    """Set the TextRun Value of a textbox."""
    val = textbox.find(f'.//{ns}Value')
    if val is not None:
        val.text = text


def _find_member_by_group(hierarchy: ET.Element, ns: str, group_name: str) -> Optional[ET.Element]:
    """Return the TablixMember whose direct Group child has the given Name."""
    for member in hierarchy.iter(f'{ns}TablixMember'):
        grp = member.find(f'{ns}Group')
        if grp is not None and grp.get('Name') == group_name:
            return member
    return None


def _rebind_group(hierarchy: ET.Element, ns: str, slot: Dict[str, Any], field: str) -> None:
    """Point a dynamic group (its expression, own sort, and header) at a new field.

    The sort expression is scoped to the group's own TablixMember so nested row groups
    (each with its own SortExpression) are rebound independently.
    """
    expr = f'=Fields!{field}.Value'
    member = _find_member_by_group(hierarchy, ns, slot['group'])
    if member is None:
        raise ValueError(f"Group '{slot['group']}' not found in template")
    ge = member.find(f'{ns}Group/{ns}GroupExpressions/{ns}GroupExpression')
    if ge is not None:
        ge.text = expr
    sort_val = member.find(f'{ns}SortExpressions/{ns}SortExpression/{ns}Value')
    if sort_val is not None:
        sort_val.text = expr
    # If this group drives pagination (Excel one-sheet-per-value), keep its PageName in sync.
    page_name = member.find(f'{ns}Group/{ns}PageName')
    if page_name is not None:
        page_name.text = expr
    # A pagination-only group may have no header textbox; rebind it only if present.
    header_name = slot.get('header_textbox')
    if header_name:
        header = hierarchy.find(f".//{ns}Textbox[@Name='{header_name}']")
        if header is not None:
            _set_value_text(header, ns, expr)


def _set_region_dataset(root: ET.Element, ns: str, tablix_name: str, dataset_name: str) -> None:
    """Point a tablix's DataSetName at the given dataset."""
    tablix = _find_tablix(root, ns, tablix_name)
    if tablix is not None:
        dsn = tablix.find(f'{ns}DataSetName')
        if dsn is not None:
            dsn.text = dataset_name


def _rebind_matrix_region(root: ET.Element, ns: str, tablix_name: str,
                          slots: Dict[str, Any], bindings: Optional[Dict[str, Any]]) -> None:
    """Rebind a matrix tablix's row group(s), column group, and value cell.

    Supports one row group (slot 'row_group' / binding 'row_group') or several nested row
    groups (slot 'row_groups' list / binding 'row_groups' list, outer-to-inner).
    """
    if not bindings:
        raise ValueError("matrix template requires 'bindings' (row group(s), column_group, value)")

    tablix = _find_tablix(root, ns, tablix_name)
    if tablix is None:
        raise ValueError(f"Template tablix '{tablix_name}' not found")
    row_hier = tablix.find(f'{ns}TablixRowHierarchy')
    col_hier = tablix.find(f'{ns}TablixColumnHierarchy')

    # Row groups: accept singular or list from both the manifest and the bindings.
    row_slots = slots.get('row_groups') or [slots['row_group']]
    row_fields = bindings.get('row_groups')
    if row_fields is None and bindings.get('row_group'):
        row_fields = [bindings['row_group']]
    if not row_fields:
        raise ValueError("bindings.row_group (or row_groups) is required")
    if len(row_fields) != len(row_slots):
        raise ValueError(f"this template expects {len(row_slots)} row group field(s), "
                         f"got {len(row_fields)}")
    if not bindings.get('column_group'):
        raise ValueError("bindings.column_group is required")
    if not bindings.get('value'):
        raise ValueError("bindings.value is required")

    labels = bindings.get('row_group_labels') or []
    for i, (slot, field) in enumerate(zip(row_slots, row_fields)):
        _rebind_group(row_hier, ns, slot, field)
        # Optional: relabel the static corner cell for this row dimension.
        if i < len(labels) and slot.get('corner_textbox'):
            corner = tablix.find(f".//{ns}Textbox[@Name='{slot['corner_textbox']}']")
            if corner is not None:
                _set_value_text(corner, ns, labels[i])

    _rebind_group(col_hier, ns, slots['column_group'], bindings['column_group'])

    aggregate = bindings.get('aggregate', slots['value'].get('default_aggregate', 'Sum'))
    value_tb = tablix.find(f".//{ns}Textbox[@Name='{slots['value']['value_textbox']}']")
    if value_tb is None:
        raise ValueError("Value textbox not found in template")
    _set_value_text(value_tb, ns, f"={aggregate}(Fields!{bindings['value']}.Value)")
    if bindings.get('value_format'):
        text_run = value_tb.find(f'.//{ns}TextRun')
        style = text_run.find(f'{ns}Style')
        if style is None:
            style = ET.SubElement(text_run, f'{ns}Style')
        fmt = style.find(f'{ns}Format')
        if fmt is None:
            fmt = ET.SubElement(style, f'{ns}Format')
        fmt.text = bindings['value_format']


def create_report_from_template(filepath: str, template: str, title: str, source_type: str,
                                connection: Dict[str, Any], dataset_name: str, query: str,
                                fields: List[Dict[str, Any]],
                                parameters: Optional[List[Dict[str, Any]]] = None,
                                bindings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a report by cloning a styled template and rebinding its data.

    Args mirror create_report, plus:
      template: a name from list_templates
      bindings: required for matrix templates — {row_group, column_group, value,
                aggregate?, value_format?} referencing field names. Ignored for table
                templates (which stamp one column per field).
    Each field may include {name, data_field?, type_name?, label?, width?, format?}.
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

    # Point the tablix at the new dataset
    _set_region_dataset(root, ns, manifest['tablix_name'], dataset_name)

    # Rebind the data region according to the template's structure
    structure = manifest.get('structure', 'table')
    try:
        if structure == 'matrix':
            _rebind_matrix_region(root, ns, manifest['tablix_name'], manifest['slots'], bindings)
            rows = (bindings or {}).get('row_groups') or [(bindings or {}).get('row_group')]
            detail = (f"matrix: rows={'/'.join(str(r) for r in rows)}, "
                      f"cols={(bindings or {}).get('column_group')}, value={(bindings or {}).get('value')}")
        else:
            _rebind_table_region(root, ns, manifest['tablix_name'], manifest['prototype'], fields)
            detail = f"{len(fields)} columns"
    except ValueError as e:
        return {'success': False, 'message': str(e)}

    if parameters:
        report_builder._add_report_parameters(root, ns, parameters)

    write_xml(tree, filepath)
    logger.info(f"Created report '{title}' from template '{template}' at {filepath}")
    return {
        'success': True,
        'message': (f"Created report '{title}' from template '{template}' ({source_type}) at "
                    f"{filepath}: dataset '{dataset_name}', {detail}, "
                    f"{len(parameters)} parameters"),
        'filepath': filepath,
    }


def create_composite_report_from_template(filepath: str, template: str, title: str,
                                          source_type: str, connection: Dict[str, Any],
                                          datasets: List[Dict[str, Any]],
                                          regions: Dict[str, Any]) -> Dict[str, Any]:
    """Create a report from a multi-region template (e.g. matrix_and_table).

    Args:
        datasets: list of {name, query, fields, parameters?} — one per dataset the template
                  expects (names must match the manifest's region datasets).
        regions: dict keyed by the manifest region name. For a matrix region:
                 {"bindings": {row_group(s), column_group, value, aggregate?, value_format?}}.
                 For a table region: {"columns": [{name, label?, width?, format?}, ...]}.
    """
    manifest = _load_manifest(template)
    if manifest is None:
        avail = [t['name'] for t in list_templates()['templates']]
        return {'success': False, 'message': f"Unknown template '{template}'. Available: {avail}"}
    if manifest.get('structure') != 'composite':
        return {'success': False,
                'message': f"Template '{template}' is not composite; use create_report_from_template."}
    if source_type not in report_builder._SOURCE_CONFIG:
        return {'success': False, 'message': f"Unknown source_type '{source_type}'. Use 'fabric' or 'sql'."}

    provided = {d['name']: d for d in datasets}
    manifest_regions = manifest['regions']
    needed_datasets = {r['dataset'] for r in manifest_regions.values()}
    missing = needed_datasets - set(provided)
    if missing:
        return {'success': False,
                'message': f"Missing dataset(s) {sorted(missing)}; this template needs {sorted(needed_datasets)}."}

    tree = parse_rdl_tree(os.path.join(_template_dir(template), 'template.rdl'))
    root = tree.getroot()
    ns = get_namespace(root)

    report_id = root.find(f'{report_builder.RD_NS}ReportID')
    if report_id is not None:
        report_id.text = str(uuid.uuid4())

    # One shared data source
    datasource_name = connection.get('name', 'DataSource1')
    connect_string = report_builder._build_connect_string(source_type, connection)
    datasources = root.find(f'{ns}DataSources')
    for ds in list(datasources):
        datasources.remove(ds)
    report_builder._add_datasource(datasources, ns, datasource_name, source_type, connect_string)

    # Rebuild all datasets
    datasets_elem = root.find(f'{ns}DataSets')
    for ds in list(datasets_elem):
        datasets_elem.remove(ds)
    all_params: List[Dict[str, Any]] = []
    for d in datasets:
        d_params = d.get('parameters', []) or []
        report_builder._add_dataset(datasets_elem, ns, d['name'], datasource_name, d['query'],
                                    d['fields'], [p['name'] for p in d_params])
        all_params.extend(d_params)

    # Rebind each region
    try:
        for region_name, region in manifest_regions.items():
            caller = regions.get(region_name, {})
            _set_region_dataset(root, ns, region['tablix_name'], region['dataset'])
            if region['kind'] == 'matrix':
                _rebind_matrix_region(root, ns, region['tablix_name'], region['slots'],
                                      caller.get('bindings'))
            elif region['kind'] == 'table':
                columns = caller.get('columns')
                if not columns:
                    raise ValueError(f"region '{region_name}' (table) requires 'columns'")
                _rebind_table_region(root, ns, region['tablix_name'], region['prototype'], columns)
            else:
                raise ValueError(f"unknown region kind '{region['kind']}'")
    except ValueError as e:
        return {'success': False, 'message': str(e)}

    if all_params:
        report_builder._add_report_parameters(root, ns, all_params)

    write_xml(tree, filepath)
    logger.info(f"Created composite report '{title}' from template '{template}' at {filepath}")
    return {
        'success': True,
        'message': (f"Created composite report '{title}' from template '{template}' "
                    f"({source_type}) at {filepath}: {len(datasets)} datasets, "
                    f"{len(manifest_regions)} regions"),
        'filepath': filepath,
    }
