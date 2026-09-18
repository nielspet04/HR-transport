"""Revised four-field bootstrap contract; other Excel fields irrelevant."""
from decimal import Decimal
import os
import pytest
from app.importers.reference import HEADERS, import_reference
from app.importers.planet import ImportSourceError
from test_planet_importer import write_xlsx


def make(tmp_path,rows):
    return write_xlsx(tmp_path/'fictional.xlsx',[list(HEADERS),*rows],sheet_name='Report')


def test_four_fields_only_and_header_offset(tmp_path):
    path=write_xlsx(tmp_path/'fictional.xlsx',[['title']]+[[]]*9+
        [list(HEADERS)+['Bedrag/eenheid'],['Voorbeeld Alex','APT',12,'Privé auto',{'formula':'X1-X2'}]],sheet_name='Report',dimension='A1:A1')
    r=import_reference(path)
    assert r.report.header_row==11
    record,=r.records
    assert record.distance==Decimal('12') and record.transport_mode=='PRIVATE_CAR'
    assert record.unresolved==()
    assert tuple(k for k,v in record.source_values)==HEADERS
    assert not hasattr(record,'amount') and not hasattr(record,'external_reference')


def test_special_rows_ignored_and_no_inheritance(tmp_path):
    r=import_reference(make(tmp_path,[['Voorbeeld Alex','APT',12,'Privé auto'],
        ['Voorbeeld Alex','APT vroeg',99,'Fiets'],[None,'Postnl Test',20,None]]))
    assert r.report.ignored_special_rows==1 and len(r.records)==2
    assert r.records[1].employee_name is None and r.records[1].transport_mode is None


@pytest.mark.parametrize('value',['40-42','Intern',None,True,-1])
def test_invalid_distance_visible(tmp_path,value):
    r=import_reference(make(tmp_path,[['Voorbeeld Alex','APT',value,'Fiets']]))
    assert r.records[0].distance is None and 'UNRESOLVED_DISTANCE' in r.records[0].unresolved


def test_conflicting_modes_per_same_location_but_not_other_location(tmp_path):
    r=import_reference(make(tmp_path,[['Voorbeeld Alex','APT',10,'Fiets'],
        ['Voorbeeld Alex','apt',10,'Privé auto'],['Voorbeeld Alex','Postnl Test',20,'Trein']]))
    assert all('CONFLICTING_PERSON_LOCATION' in x.unresolved for x in r.records[:2])
    assert r.records[2].unresolved==()


def test_metadata_only_rows_ignored_reconciliation(tmp_path):
    r=import_reference(make(tmp_path,[['Voorbeeld Alex',None,None,None],[],list(HEADERS),
        ['Voorbeeld Alex','APT',0,'Dienstwagen']]))
    p=r.report
    assert p.ignored_nondata_rows==1 and p.imported_rows==1
    assert p.data_rows_seen==p.blank_rows+p.repeated_header_rows+p.ignored_nondata_rows+p.ignored_special_rows+p.imported_rows


def test_missing_sheet_header_fails(tmp_path):
    path=write_xlsx(tmp_path/'bad.xlsx',[['Naam','Locatie','Afstand']],sheet_name='Report')
    with pytest.raises(ImportSourceError):import_reference(path)


@pytest.mark.skipif(not os.environ.get('REFERENCE_SOURCE'),reason='Private optional reference')
def test_private_only_requested_fields():
    r=import_reference(os.environ['REFERENCE_SOURCE'])
    assert r.report.header_row==11
    assert all(tuple(k for k,v in x.source_values)==HEADERS for x in r.records)
    assert not any('vroeg' in (x.location or '').casefold() for x in r.records)
