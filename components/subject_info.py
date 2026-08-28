


import common.db_schema as db_schema
import common.locale_manager as locale_manager

class ESISubjectInfo:
    def __init__(self, name_en, name_ch):
        self.use_institution_subject = False
        self.nameCH = name_ch
        self.nameEN = name_en

    @property
    def name(self) -> str:
        if locale_manager.lang == "zh-TW":
            return self.nameCH
        else:
            return self.nameEN
   

## PR_ESI 的 isAC 預設為true
class ESIInstitutionSubjectInfo(ESISubjectInfo):
    def get_subject(self,selected_values: list[str], only_fetch_selected : bool = False, is_ac : bool = True, selected_all : bool = False) -> tuple["Subject", dict[str, "Column"]]:
        from dal_provider import get_dal
        dal = get_dal()
        self.use_institution_subject = True

        # SetMainTable(schema.ESIRawDataForInstitutionTableName);
        db_schema.schema.MainTableName = db_schema.schema.ESIRawDataForInstitutionTableName

        tbl = dal.create_table(db_schema.schema.ESIRawDataForInstitutionTableName)
        col_inst= tbl.RetrieveColumn(db_schema.schema.InstitutionColumnName)

        subj = None

        if is_ac:
            tbl_ac_first = dal.create_table(db_schema.schema.ACFirstTableName)
            col_esi_ac_main = tbl_ac_first.RetrieveColumn(db_schema.schema.ESIACMainColumnName)
            col_org_serial = tbl_ac_first.RetrieveColumn(db_schema.schema.OrgSerialColumnName)
            col_ac_word = tbl_ac_first.RetrieveColumn(db_schema.schema.ACWordColumnName)
            col_time_end = tbl_ac_first.RetrieveColumn(db_schema.schema.Time_EndColumnName)

            on = dal.create_join_on(col_inst, col_ac_word)
            jtb = dal.create_join_table(tbl, tbl_ac_first, dal.JOINTYPE.InnerJoin, on)

            subj = dal.create_subject(jtb, col_org_serial)
            subj.Initialize()

            restric_esi_ac_main = dal.create_where_column_to_const(col_esi_ac_main, dal.OPTYPE.Equal, "1")
            restric_time_end = dal.create_where_null(col_time_end, dal.OPTYPE.Is)

            if selected_all :
                subj.addAll(dal.to_csharp_array([restric_esi_ac_main, restric_time_end]))
            else:
                for serial in selected_values:
                    subj.Add(serial, dal.to_csharp_array([restric_esi_ac_main, restric_time_end]))
        else:
            ## ESI不會跑到這，先不實作
            pass

        return subj, {db_schema.schema.InstitutionColumnName : col_inst}
   
class ESIFieldSubjectInfo(ESISubjectInfo):
    def get_subject(self,selected_values: list[str], only_fetch_selected : bool = False, shown_by_esiid:bool = False,  selected_all : bool = False) -> tuple["Subject", dict[str, "Column"]]:
        self.use_institution_subject = False

        return self.get_field_subject(selected_values, db_schema.schema.MainTableName, shown_by_esiid, selected_all)

    def get_field_subject(self,selected_fids: list[str], main_table_name:str, shown_by_esiid:bool = True,  selected_all : bool = False)-> tuple["Subject", dict[str, "Column"]]:
        from dal_provider import get_dal
        dal = get_dal()

        tbl_paper_field_esi = dal.create_table(db_schema.schema.PaperFieldESITableName)
        tbl_field = dal.create_table(main_table_name)

        col_FID = tbl_paper_field_esi.RetrieveColumn(db_schema.schema.FIDColumnName)
        col_ESIID = tbl_paper_field_esi.RetrieveColumn(db_schema.schema.ESIIDColumnName)
        col_category = tbl_field.RetrieveColumn(db_schema.schema.ESICategoryColumnName)

        on = dal.create_join_on(col_ESIID, col_category)
        jtb = dal.create_join_table(tbl_paper_field_esi, tbl_field, dal.JOINTYPE.InnerJoin, on)

        subj = None

        if shown_by_esiid:
            subj = dal.create_subject(jtb, col_FID, col_ESIID)
        else:
            subj = dal.create_subject(jtb, col_FID)

        subj.Initialize()

        if selected_all:
            subj.addAll()
        else:
            arr = dal.to_csharp_array(selected_fids)
            subj.AddRange(arr)

        return subj, {db_schema.schema.ESICategoryColumnName: col_category}
