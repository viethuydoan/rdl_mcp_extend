"""Tests for report_builder.create_report (Phase 2: fabric + sql sources)."""

import xml.etree.ElementTree as ET

from rdl_report_mcp import report_builder, validation

NS = '{http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition}'


def _make(tmp_path, source_type, **over):
    fp = str(tmp_path / f'{source_type}.rdl')
    args = dict(
        filepath=fp, title='T', source_type=source_type,
        connection={'name': 'ds', 'data_source': 'srv', 'initial_catalog': 'db'},
        dataset_name='data', query='SELECT 1 AS x',
        fields=[{'name': 'x', 'type_name': 'System.Int32'}],
    )
    args.update(over)
    res = report_builder.create_report(**args)
    return fp, res


def test_fabric_report_structure(tmp_path):
    fp, res = _make(tmp_path, 'fabric')
    assert res['success']
    txt = open(fp, encoding='utf-8').read()
    # Clean namespace round-trip (the bug we fixed)
    assert 'ns0:' not in txt
    assert txt.splitlines()[1].startswith('<Report xmlns="http://schemas.microsoft.com')
    # Provider + Fabric auth
    assert '<DataProvider>SQLAZURE</DataProvider>' in txt
    assert 'Authentication=ActiveDirectoryInteractive' in txt
    assert validation.validate_rdl(fp)['valid'] is True


def test_sql_report_structure(tmp_path):
    fp, res = _make(tmp_path, 'sql')
    assert res['success']
    txt = open(fp, encoding='utf-8').read()
    assert '<DataProvider>SQL</DataProvider>' in txt
    assert '<rd:SecurityType>Integrated</rd:SecurityType>' in txt
    assert 'Authentication=' not in txt  # plain SQL has no AAD auth suffix
    assert validation.validate_rdl(fp)['valid'] is True


def test_parameters_create_query_params_and_report_params(tmp_path):
    fp, _ = _make(tmp_path, 'fabric',
                  query='SELECT x WHERE m IN (@Month)',
                  parameters=[{'name': 'Month', 'data_type': 'String',
                               'prompt': 'Pick month', 'default': '2026-01-01'}])
    root = ET.parse(fp).getroot()
    # QueryParameter on the dataset
    qp = root.find(f'.//{NS}QueryParameter')
    assert qp is not None and qp.get('Name') == '@Month'
    assert qp.find(f'{NS}Value').text == '=Parameters!Month.Value'
    # ReportParameter inserted after DataSets, before ReportSections
    children = [c.tag for c in list(root)]
    assert children.index(f'{NS}ReportParameters') < children.index(f'{NS}ReportSections')
    rp = root.find(f'.//{NS}ReportParameter')
    assert rp.get('Name') == 'Month'
    assert rp.find(f'{NS}Prompt').text == 'Pick month'


def test_explicit_connect_string_override(tmp_path):
    fp, _ = _make(tmp_path, 'fabric',
                  connection={'name': 'c', 'connect_string': 'Data Source=X;Initial Catalog=Y'})
    txt = open(fp, encoding='utf-8').read()
    assert '<ConnectString>Data Source=X;Initial Catalog=Y</ConnectString>' in txt


def test_unknown_source_type_fails(tmp_path):
    _, res = _make(tmp_path, 'oracle')
    assert res['success'] is False
