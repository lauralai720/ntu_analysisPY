from typing import Optional

from components.subject_info import *

class DBSchema:
    MainTableName = None
    MainBindColumnName = None
    TimeColumnName = None
    RefTableName = None
    ReferColumnName = None
    CitedColumnName = None
    CountryTableName = None
    CountryColumnName = None
    CountryCodeColumnName = None
    ContinentColumnName = None


class ESISchema(DBSchema):
    ESIRawDataVersionTableName = "AC_Manager.dbo.EsiRawDataVersion"
    ESIRawDataForInstitutionTableName = "AC_Manager.dbo.EsiRawDataForInstitution"
    ESIRawDataForResearchFieldTableName = "AC_Manager.dbo.EsiRawDataForResearchField"
    ACFirstTableName = "AC_Manager.dbo.ACFirst"
    ESIHiCiTableName = "AC_Manager.dbo.EsiHiCi"
    OrgScaleTableName = "AC_Manager.dbo.OrgScale"
    EsiAcAttrInfoTableName = "AC_Manager.dbo.EsiAcAttrInfo"
    PaperFieldGroupTableName = "AC_Manager.dbo.Paper_Field_Group"
    PaperFieldInfoTableName = "AC_Manager.dbo.Paper_Field_info"
    PaperFieldESITableName = "AC_Manager.dbo.Paper_Field_ESI"
    NationTableName = "AC_Manager.dbo.Nation"
    OrgFirstTableName = "AC_Manager.dbo.OrgFirst"
    ESIUpdateTimeColumnName = "EsiUpdateTime"
    DataRangeStartColumnName = "DataRangeStart"
    DataRangeEndColumnName = "DataRangeEnd"
    InstitutionColumnName = "Institution"
    OrgSerialColumnName = "OrgSerial"
    ESIACMainColumnName = "ESI_AC_Main"
    Time_EndColumnName = "Time_End"
    TimeStartColumnName = "TimeStart"
    TimeEndColumnName = "TimeEnd"
    ACWordColumnName = "AC_Word"
    PaperCountColumnName = "PaperCount"
    TableIdColumnName = "TableId"
    TableNameColumnName = "TableName"
    IdColumnName = "Id"
    ESICategoryColumnName = "EsiCategory"
    CiteColumnName = "Cite"
    HighlyCitedPaperCountColumnName = "HighlyCitedPaperCount"
    HotPaperColumnName = "HotPaperCount"
    PeriodColumnName = "Period"
    ScaleNumberColumnName = "ScaleNumber"
    DataYearColumnName = "DataYear"
    CitesPerPaperColumnName = "CitesPerPaper"
    EsiACColumnName = "EsiAc"
    CountrySerialColumnName = "CountrySerial"
    ContinentColumnName = "Continent"
    GroupNameColumnName = "Group_Name"
    FieldNameCHColumnName = "Field_Name_CH"
    FGIDColumnName = "FGID"
    FIDColumnName = "FID"
    ESIIDColumnName = "ESI_ID"
    OrgNameCHColumnName = "OrgName_CH"
    OrgNameENColumnName = "OrgName_EN"
    CountryNameCHColumnName = "CountryName_CH"
    CountryNameENColumnName = "CountryName_EN"
    CountryColumnName = "Country"
    EsiStatusColumnName = "ESI_Status"

    ESIInstitutionInfo : ESIInstitutionSubjectInfo = None
    ESIFieldInfo : ESIFieldSubjectInfo = None




schema : Optional[ESISchema] = None