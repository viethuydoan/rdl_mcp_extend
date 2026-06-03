"""Scaffold brand-new RDL reports from scratch.

Phase 2 supports SQL-style data sources:
  - source_type="fabric": Microsoft Fabric SQL endpoint (DataProvider=SQLAZURE,
    Authentication=ActiveDirectoryInteractive)
  - source_type="sql":    on-prem / Azure SQL Server (DataProvider=SQL, integrated security)

Both produce an embedded T-SQL dataset. The body is left empty (no visuals yet) — matrix
and table authoring come in later phases. The generated report opens in Report Builder and
its dataset query can be run to return rows.

DAX / Power BI semantic-model sources are added in Phase 3.
"""

import os
import uuid
import logging
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional

from .xml_utils import parse_rdl_tree, get_namespace, write_xml

logger = logging.getLogger(__name__)

RD_NS = '{http://schemas.microsoft.com/SQLServer/reporting/reportdesigner}'
_TEMPLATES = os.path.join(os.path.dirname(__file__), 'templates')

# Per-source-type DataSource configuration.
_SOURCE_CONFIG = {
    'fabric': {
        'provider': 'SQLAZURE',
        'security_type': 'None',
        # Fabric warehouse / lakehouse SQL endpoint.
        'auth_suffix': ';Authentication=ActiveDirectoryInteractive',
    },
    'sql': {
        'provider': 'SQL',
        'security_type': 'Integrated',
        'auth_suffix': '',
    },
    'dax': {
        # Power BI semantic model (Analysis Services) queried with DAX.
        'provider': 'PBIDATASET',
        'security_type': 'None',
        'auth_suffix': '',
    },
}


def _build_connect_string(source_type: str, connection: Dict[str, Any]) -> str:
    """Build the ConnectString, honoring an explicit override if provided."""
    if connection.get('connect_string'):
        return connection['connect_string']
    if source_type == 'dax':
        # pbiazure connection to a Power BI semantic model. Identity Provider (with tenant
        # GUID) is environment-specific; pass it via connection['identity_provider'] or supply
        # a full connect_string. Initial Catalog is the model/dataset GUID.
        data_source = connection.get('data_source', 'pbiazure://api.powerbi.com/')
        initial_catalog = connection.get('initial_catalog', '')
        idp = connection.get('identity_provider')
        idp_part = f';Identity Provider="{idp}"' if idp else ''
        return (f'Data Source={data_source}{idp_part};Initial Catalog={initial_catalog};'
                f'Integrated Security=ClaimsToken')
    data_source = connection.get('data_source', '')
    initial_catalog = connection.get('initial_catalog', '')
    suffix = _SOURCE_CONFIG[source_type]['auth_suffix']
    return f'Data Source={data_source};Initial Catalog={initial_catalog}{suffix}'


def _add_datasource(datasources: ET.Element, ns: str, name: str, source_type: str,
                    connect_string: str, connection: Optional[Dict[str, Any]] = None) -> None:
    """Append a <DataSource> (child order mirrors a working PBIRB report)."""
    cfg = _SOURCE_CONFIG[source_type]
    connection = connection or {}
    ds = ET.SubElement(datasources, f'{ns}DataSource')
    ds.set('Name', name)

    sec = ET.SubElement(ds, f'{RD_NS}SecurityType')
    sec.text = cfg['security_type']

    conn_props = ET.SubElement(ds, f'{ns}ConnectionProperties')
    provider = ET.SubElement(conn_props, f'{ns}DataProvider')
    provider.text = cfg['provider']
    conn = ET.SubElement(conn_props, f'{ns}ConnectString')
    conn.text = connect_string

    ds_id = ET.SubElement(ds, f'{RD_NS}DataSourceID')
    ds_id.text = str(uuid.uuid4())

    # Power BI semantic-model datasources carry the workspace + dataset names.
    if source_type == 'dax':
        ws = ET.SubElement(ds, f'{RD_NS}PowerBIWorkspaceName')
        ws.text = connection.get('workspace_name', '')
        pds = ET.SubElement(ds, f'{RD_NS}PowerBIDatasetName')
        pds.text = connection.get('dataset_name', '')


def _add_field(fields_elem: ET.Element, ns: str, field: Dict[str, Any]) -> None:
    """Append a <Field> with DataField + rd:TypeName."""
    name = field['name']
    data_field = field.get('data_field', name)
    type_name = field.get('type_name', 'System.String')

    f = ET.SubElement(fields_elem, f'{ns}Field')
    f.set('Name', name)
    df = ET.SubElement(f, f'{ns}DataField')
    df.text = data_field
    tn = ET.SubElement(f, f'{RD_NS}TypeName')
    tn.text = type_name


def _add_dataset(datasets: ET.Element, ns: str, name: str, datasource_name: str,
                 query: str, fields: List[Dict[str, Any]],
                 query_parameters: List[str]) -> None:
    """Append a <DataSet> with embedded SQL CommandText + Fields."""
    ds = ET.SubElement(datasets, f'{ns}DataSet')
    ds.set('Name', name)

    q = ET.SubElement(ds, f'{ns}Query')
    dsn = ET.SubElement(q, f'{ns}DataSourceName')
    dsn.text = datasource_name

    if query_parameters:
        qparams = ET.SubElement(q, f'{ns}QueryParameters')
        for pname in query_parameters:
            qp = ET.SubElement(qparams, f'{ns}QueryParameter')
            qp.set('Name', f'@{pname}')
            val = ET.SubElement(qp, f'{ns}Value')
            val.text = f'=Parameters!{pname}.Value'

    cmd = ET.SubElement(q, f'{ns}CommandText')
    cmd.text = query

    fields_elem = ET.SubElement(ds, f'{ns}Fields')
    for field in fields:
        _add_field(fields_elem, ns, field)


def _add_report_parameters(root: ET.Element, ns: str,
                           parameters: List[Dict[str, Any]]) -> None:
    """Insert <ReportParameters> after <DataSets> (schema order)."""
    report_params = ET.Element(f'{ns}ReportParameters')
    for p in parameters:
        rp = ET.SubElement(report_params, f'{ns}ReportParameter')
        rp.set('Name', p['name'])
        dt = ET.SubElement(rp, f'{ns}DataType')
        dt.text = p.get('data_type', 'String')
        if p.get('default') is not None:
            dv = ET.SubElement(rp, f'{ns}DefaultValue')
            vals = ET.SubElement(dv, f'{ns}Values')
            v = ET.SubElement(vals, f'{ns}Value')
            v.text = str(p['default'])
        prompt = ET.SubElement(rp, f'{ns}Prompt')
        prompt.text = p.get('prompt', p['name'])

    datasets = root.find(f'{ns}DataSets')
    idx = list(root).index(datasets) + 1 if datasets is not None else len(list(root))
    root.insert(idx, report_params)


def create_report(filepath: str, title: str, source_type: str,
                  connection: Dict[str, Any], dataset_name: str, query: str,
                  fields: List[Dict[str, Any]],
                  parameters: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Create a new paginated report with one SQL-style data source and dataset.

    Args:
        filepath: output path for the new .rdl file
        title: report title (informational for now; surfaced in the result message)
        source_type: "fabric" (SQLAZURE) or "sql" (SQL Server)
        connection: dict with either 'connect_string', or 'data_source'+'initial_catalog';
                    optional 'name' for the DataSource element (default "DataSource1")
        dataset_name: name of the dataset
        query: embedded T-SQL CommandText
        fields: list of {name, data_field?, type_name?}
        parameters: optional list of {name, data_type?, prompt?, default?}; each also
                    becomes a @name QueryParameter on the dataset
    """
    if source_type not in _SOURCE_CONFIG:
        return {'success': False,
                'message': f"Unknown source_type '{source_type}'. Use 'fabric' or 'sql'."}
    if not fields:
        return {'success': False, 'message': 'At least one field is required.'}

    parameters = parameters or []
    skeleton = os.path.join(_TEMPLATES, 'report_skeleton_sql.rdl')
    tree = parse_rdl_tree(skeleton)
    root = tree.getroot()
    ns = get_namespace(root)

    # Fresh report id
    report_id = root.find(f'{RD_NS}ReportID')
    if report_id is not None:
        report_id.text = str(uuid.uuid4())

    datasource_name = connection.get('name', 'DataSource1')
    connect_string = _build_connect_string(source_type, connection)

    datasources = root.find(f'{ns}DataSources')
    _add_datasource(datasources, ns, datasource_name, source_type, connect_string, connection)

    # DAX datasets don't use @name QueryParameters (the SQL pattern); skip auto-wiring them.
    query_parameters = [] if source_type == 'dax' else [p['name'] for p in parameters]
    datasets = root.find(f'{ns}DataSets')
    _add_dataset(datasets, ns, dataset_name, datasource_name, query, fields, query_parameters)

    if parameters:
        _add_report_parameters(root, ns, parameters)

    write_xml(tree, filepath)
    logger.info(f"Created report '{title}' at {filepath}")
    return {
        'success': True,
        'message': (f"Created report '{title}' ({source_type}) at {filepath} with dataset "
                    f"'{dataset_name}' ({len(fields)} fields, {len(parameters)} parameters)"),
        'filepath': filepath,
    }


def add_dataset(filepath: str, dataset_name: str, query: str,
                fields: List[Dict[str, Any]], datasource_name: Optional[str] = None) -> Dict[str, Any]:
    """Append an additional dataset to an existing report.

    Binds the dataset to an existing data source (``datasource_name``, or the first one in
    the report if omitted) — useful for adding parameter-value / lookup datasets that share
    the report's connection. ``fields`` items are {name, data_field?, type_name?}.
    """
    if not fields:
        return {'success': False, 'message': 'At least one field is required.'}

    tree = parse_rdl_tree(filepath)
    root = tree.getroot()
    ns = get_namespace(root)

    datasources = root.find(f'{ns}DataSources')
    available = [d.get('Name') for d in datasources.findall(f'{ns}DataSource')] if datasources is not None else []
    if not available:
        return {'success': False, 'message': 'Report has no data source to bind the dataset to.'}
    if datasource_name is None:
        datasource_name = available[0]
    elif datasource_name not in available:
        return {'success': False,
                'message': f"Data source '{datasource_name}' not found. Available: {available}"}

    datasets = root.find(f'{ns}DataSets')
    if datasets is None:
        # Insert a DataSets element right after DataSources (schema order)
        datasets = ET.Element(f'{ns}DataSets')
        root.insert(list(root).index(datasources) + 1, datasets)
    for existing in datasets.findall(f'{ns}DataSet'):
        if existing.get('Name') == dataset_name:
            return {'success': False, 'message': f"Dataset '{dataset_name}' already exists."}

    _add_dataset(datasets, ns, dataset_name, datasource_name, query, fields, [])

    write_xml(tree, filepath)
    logger.info(f"Added dataset '{dataset_name}' to {filepath}")
    return {
        'success': True,
        'message': (f"Added dataset '{dataset_name}' ({len(fields)} fields) bound to data "
                    f"source '{datasource_name}'"),
        'filepath': filepath,
    }
