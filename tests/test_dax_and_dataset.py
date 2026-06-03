"""Tests for DAX (Power BI semantic model) source + add_dataset (Phase 3)."""

import xml.etree.ElementTree as ET

from rdl_report_mcp import report_builder, templates_lib, validation

NS = '{http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition}'
RD = report_builder.RD_NS


def test_create_report_dax(tmp_path):
    fp = str(tmp_path / 'dax.rdl')
    res = report_builder.create_report(
        filepath=fp, title='T', source_type='dax',
        connection={'name': 'pbi', 'initial_catalog': 'model-guid',
                    'identity_provider': 'idp-string',
                    'workspace_name': 'WS', 'dataset_name': 'Model'},
        dataset_name='d',
        query='EVALUATE SUMMARIZECOLUMNS(T[A], "M", [Measure])',
        fields=[{'name': 'A', 'data_field': 'T[A]'},
                {'name': 'M', 'data_field': '[Measure]', 'type_name': 'System.Decimal'}])
    assert res['success']
    root = ET.parse(fp).getroot()
    assert root.find(f'.//{NS}DataProvider').text == 'PBIDATASET'
    cs = root.find(f'.//{NS}ConnectString').text
    assert 'pbiazure://api.powerbi.com/' in cs and 'ClaimsToken' in cs and 'idp-string' in cs
    assert root.find(f'.//{RD}PowerBIWorkspaceName').text == 'WS'
    assert root.find(f'.//{RD}PowerBIDatasetName').text == 'Model'
    # DAX DataFields preserved as Table[Col] / [Measure]
    dfs = [f.find(f'{NS}DataField').text for f in root.findall(f'.//{NS}Field')]
    assert dfs == ['T[A]', '[Measure]']
    assert validation.validate_rdl(fp)['valid'] is True


def test_dax_connect_string_override(tmp_path):
    fp = str(tmp_path / 'dax2.rdl')
    report_builder.create_report(
        filepath=fp, title='T', source_type='dax',
        connection={'name': 'pbi', 'connect_string': 'Data Source=X;Initial Catalog=Y;Integrated Security=ClaimsToken'},
        dataset_name='d', query='EVALUATE ROW("x",1)', fields=[{'name': 'x', 'data_field': '[x]'}])
    txt = open(fp, encoding='utf-8').read()
    assert '<ConnectString>Data Source=X;Initial Catalog=Y;Integrated Security=ClaimsToken</ConnectString>' in txt


def test_dax_template_matrix(tmp_path):
    fp = str(tmp_path / 'daxm.rdl')
    res = templates_lib.create_report_from_template(
        filepath=fp, template='simple_matrix', title='M', source_type='dax',
        connection={'name': 'pbi', 'connect_string': 'Data Source=X;Initial Catalog=Y;Integrated Security=ClaimsToken',
                    'workspace_name': 'WS', 'dataset_name': 'DS'},
        dataset_name='m', query='EVALUATE SUMMARIZECOLUMNS(T[R],T[C],"V",[Mea])',
        fields=[{'name': 'R', 'data_field': 'T[R]'}, {'name': 'C', 'data_field': 'T[C]'},
                {'name': 'V', 'data_field': '[Mea]', 'type_name': 'System.Decimal'}],
        bindings={'row_group': 'R', 'column_group': 'C', 'value': 'V'})
    assert res['success']
    root = ET.parse(fp).getroot()
    assert root.find(f'.//{NS}DataProvider').text == 'PBIDATASET'
    assert root.find(f'.//{RD}PowerBIDatasetName').text == 'DS'
    assert validation.validate_rdl(fp)['valid'] is True


def test_add_dataset(tmp_path):
    fp = str(tmp_path / 'r.rdl')
    report_builder.create_report(
        filepath=fp, title='T', source_type='fabric',
        connection={'name': 'fab', 'data_source': 's', 'initial_catalog': 'd'},
        dataset_name='main', query='SELECT a FROM t', fields=[{'name': 'a'}])
    res = report_builder.add_dataset(fp, dataset_name='param_vals',
                                     query='SELECT DISTINCT region FROM t',
                                     fields=[{'name': 'region'}])
    assert res['success'], res['message']
    root = ET.parse(fp).getroot()
    names = [d.get('Name') for d in root.findall(f'.//{NS}DataSet')]
    assert names == ['main', 'param_vals']
    # bound to the existing data source
    pv = [d for d in root.findall(f'.//{NS}DataSet') if d.get('Name') == 'param_vals'][0]
    assert pv.find(f'{NS}Query/{NS}DataSourceName').text == 'fab'
    assert validation.validate_rdl(fp)['valid'] is True


def test_add_dataset_duplicate_fails(tmp_path):
    fp = str(tmp_path / 'r2.rdl')
    report_builder.create_report(
        filepath=fp, title='T', source_type='fabric',
        connection={'name': 'fab', 'data_source': 's', 'initial_catalog': 'd'},
        dataset_name='main', query='SELECT a FROM t', fields=[{'name': 'a'}])
    res = report_builder.add_dataset(fp, 'main', 'SELECT a FROM t', [{'name': 'a'}])
    assert res['success'] is False and 'already exists' in res['message']
