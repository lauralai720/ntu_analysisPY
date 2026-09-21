from dataclasses import dataclass,field
from typing import Protocol,Any

import common.db_schema as db_schema
import common.locale_manager as locale_manager
from exceptions import PRISError

class GetSubject(Protocol):
    def get_subject(self,selected_values: list[str], only_fetch_selected : bool = False, is_ac : bool = True, selected_all : bool = False) -> tuple["Subject", dict[str, "Column"], Any, str, str]:
        pass

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
    def get_subject(self,selected_values: list[str], only_fetch_selected : bool = False, is_ac : bool = True, selected_all : bool = False) -> tuple["Subject", dict[str, "Column"], Any, str,str]:
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

        return subj, {db_schema.schema.InstitutionColumnName : col_inst}, selected_values, self.nameCH, self.nameEN 
   
class ESIFieldSubjectInfo(ESISubjectInfo):
    def get_subject(self,selected_values: list[str], only_fetch_selected : bool = False, shown_by_esiid:bool = False,  selected_all : bool = False) -> tuple["Subject", dict[str, "Column"],Any , str, str]:
        
        self.use_institution_subject = False
        return self.get_field_subject(selected_values, db_schema.schema.MainTableName, shown_by_esiid, selected_all)

    def get_field_subject(self,selected_fids: list[str], main_table_name:str, shown_by_esiid:bool = True,  selected_all : bool = False)-> tuple["Subject", dict[str, "Column"],Any , str, str]:
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

        return subj, {db_schema.schema.ESICategoryColumnName: col_category}, selected_fids, self.nameCH, self.nameEN 

@dataclass
class PaperOrg1ItemKey:
    OrgNameCH = "OrgName1"
    OrgNameEN = "OrgName2"
    OrgSerial = "OrgSerial"

class PaperOrg2ItemKey:
    OrgNameCH1 = "Name1CH"
    OrgNameCH2 = "Name2CH"
    OrgNameCH3 = "Name3CH"
    OrgNameCH4 = "Name4CH"
    OrgNameEN1 = "Name1EN"
    OrgNameEN2 = "Name2EN"
    OrgNameEN3 = "Name3EN"
    OrgNameEN4 = "Name4EN"
    OrgSerial = "OrgSerial"


from components.paper_org_value import *

class WOSPaperOrgSubjectInfo:
    def __init__(self, selected_values: list[str]):
        self.orgs_selected_list:list[PaperOrg] = []
        self.order_orgs_selected_list:list[PaperOrg] = []
        self.orgs_1st_list: list[PaperOrg] = []
        self.orgs_2nd_list: list[PaperOrg] = []
        self._fetch_all_orgs(selected_values)

    def _fetch_all_orgs(self, selected_values: list[str]):
        from dal_provider import get_dal
        dal = get_dal()
        orgs_1st = []
        orgs_2nd = []
        org_like = None
        sort : bool = False

        if len(selected_values) == 1 and len(selected_values[0]) == 9:
            # 一級機構
            org_like = selected_values[0]
            sort = True
        else:
            for x in selected_values:
                if len(x) <= 9:
                    orgs_1st.append(x)
                else:
                    orgs_2nd.append(x)

            if orgs_2nd:
                sort = True

        cmd_orgs_1st_clause = None
        if org_like:
            cmd_orgs_1st_clause = f" LIKE '{org_like}%'"
        else:
            cmd_orgs_1st_clause = "', '".join(orgs_1st)
            cmd_orgs_1st_clause = f" IN ('{cmd_orgs_1st_clause}')"
            
            
        if cmd_orgs_1st_clause:   
            query_all_1st_str = (
                f"SELECT {db_schema.schema.OrgSerialColumnName}, "+
                f"{db_schema.schema.OrgNameCHColumnName}, "+
                f"{db_schema.schema.OrgNameENColumnName} "+
                f"FROM {db_schema.schema.OrgInfoTableName} "+
                f"WHERE {db_schema.schema.OrgSerialColumnName} COLLATE SQL_Latin1_General_CP1_CI_AS IN (SELECT DISTINCT {db_schema.schema.OrgColumnName} FROM {db_schema.schema.Org1stTableName}) "+
                f"AND {db_schema.schema.OrgNameCHColumnName} IS NOT NULL AND {db_schema.schema.OrgNameENColumnName} IS NOT NULL "
            )
            cmd_1st_str = (
                f"SELECT {db_schema.schema.OrgSerialColumnName}, "+
                f"{db_schema.schema.OrgNameCHColumnName}, "+
                f"{db_schema.schema.OrgNameENColumnName} "+
                f"FROM ({query_all_1st_str}) AS A "+
                #f"WHERE {db_schema.schema.OrgSerialColumnName} IN ('{cmd_orgs_1st_clause}') "
                f"WHERE {db_schema.schema.OrgSerialColumnName} {cmd_orgs_1st_clause} "
            )
            orgs_1st_list = dal.query_2d_raw(cmd_1st_str)
            for org1 in orgs_1st_list:
                #self.orgs_selected_list.append(PaperOrg(org1[0],org1[1],org1[2]))
                org_item = PaperOrg(org1[0],org1[1],org1[2])
                self.add_paper_org(self.orgs_selected_list, org_item)
                self.add_paper_org(self.orgs_1st_list, org_item)

        cmd_orgs_2nd_clause = None
        if org_like:
            cmd_orgs_2nd_clause = f" LIKE '{org_like}%'"
        else:
            cmd_orgs_2nd_clause = "', '".join(orgs_2nd)
            cmd_orgs_2nd_clause = f" IN ('{cmd_orgs_2nd_clause}')"
            
        if cmd_orgs_2nd_clause:
            query_all_2nd_str = (
                f"SELECT DISTINCT {db_schema.schema.OrgSerialColumnName}, " +
                f"{db_schema.schema.OrgName1CHColumnName}, " +
                f"{db_schema.schema.OrgName2CHColumnName}, " +
                f"{db_schema.schema.OrgName3CHColumnName}, " +
                f"{db_schema.schema.OrgName4CHColumnName}, " +
                f"{db_schema.schema.OrgName1ENColumnName}, " +
                f"{db_schema.schema.OrgName2ENColumnName}, " +
                f"{db_schema.schema.OrgName3ENColumnName}, " +
                f"{db_schema.schema.OrgName4ENColumnName} " +
                f"FROM {db_schema.schema.OrgAcSecondTableName} " +
                f"WHERE {db_schema.schema.OrgSerialColumnName} COLLATE SQL_Latin1_General_CP1_CI_AS IN (SELECT DISTINCT {db_schema.schema.OrgColumnName} FROM {db_schema.schema.Org2ndTableName}) " +
                f"AND {db_schema.schema.OrgSerialColumnName} != '' AND {db_schema.schema.OrgSerialColumnName} NOT LIKE 'XXX%'"
            )
            cmd_2nd_str = (
                f"SELECT {db_schema.schema.OrgSerialColumnName}, " +
                f"{db_schema.schema.OrgName1CHColumnName}, " +
                f"{db_schema.schema.OrgName2CHColumnName}, " +
                f"{db_schema.schema.OrgName3CHColumnName}, " +
                f"{db_schema.schema.OrgName4CHColumnName}, " +
                f"{db_schema.schema.OrgName1ENColumnName}, " +
                f"{db_schema.schema.OrgName2ENColumnName}, " +
                f"{db_schema.schema.OrgName3ENColumnName}, " +
                f"{db_schema.schema.OrgName4ENColumnName} " +
                f"FROM ({query_all_2nd_str}) AS A "+
                #f"WHERE {db_schema.schema.OrgSerialColumnName} IN ('{cmd_orgs_2nd_clause}') "
                f"WHERE {db_schema.schema.OrgSerialColumnName} {cmd_orgs_2nd_clause} "
            )
            orgs_2nd_list = dal.query_2d_raw(cmd_2nd_str)

            for org2 in orgs_2nd_list:
                org_item = PaperOrg2nd(org2[0],org2[1],org2[2],org2[3],org2[4],org2[5],org2[6],org2[7],org2[8])
                self.add_paper_org(self.orgs_selected_list, org_item)
                self.add_paper_org(self.orgs_2nd_list, org_item)

            # sort
            if sort:
                sort_selected_list = sorted(self.orgs_selected_list, key=lambda x: x.org_serial, reverse=True)
                self.orgs_selected_list = sort_selected_list
            print(f"總共所要分析的機構數量 : {len(self.orgs_selected_list)}")

    def add_paper_org(self,ret : list[PaperOrg], paper_org : PaperOrg):
        added = False
        for check in ret:
            if paper_org.org_serial == check.org_serial:
                if len(paper_org.name_ch) <= len(check.name_ch) and len(paper_org.name_en) <= len(check.name_en):
                    added = True
                else:
                    ret.remove(check)
                    break
        if added == False:
            ret.append(paper_org)
        

    def get_new_org2_list(self, filter_str:str, flag:int=0)->list[PaperOrg] :
        from dal_provider import get_dal
        dal = get_dal()
        if flag == 1:
            cmd_str = PaperSQLCmd.get_value_where_like_org_25nd_cmd(filter_str)
        else:
            cmd_str = PaperSQLCmd.get_value_where_like_org_2nd_cmd(filter_str)

        query_res = dal.query_2d_raw(cmd_str)
        res : list[PaperOrg] = []
        for org2 in query_res:
            #print(f"new org : {org2[0]}")
            org_item = PaperOrg2nd(org2[0],org2[1],org2[2],org2[3],org2[4],org2[5],org2[6],org2[7],org2[8])
            self.add_paper_org(res, org_item)
        return res

    def new_refresh_orgs(self)-> PaperOrgSelectedValue:
        res = PaperOrgSelectedValue()
        dict_res = {}
        org_2nd_filter : str|None = None
        def new_add_ret(dict_res : dict[str, PaperOrgSelectItem], org_list:list[PaperOrg], org_23nd_check : bool = True):
            for new_org in org_list:
                serial_13_str = new_org.org_serial[0:13]
                serial = new_org.org_serial
                if org_23nd_check:
                    # exist = [x for x in org_list if x.org_serial.startswith(serial_13_str) and x.org_serial != serial]
                    if serial[11:13] != "00" and serial[13:15] == "00":
                        incorporate_serial = f"{serial_13_str}%"
                        dict_res[incorporate_serial] = PaperOrgSelectItem(incorporate_serial, new_org.name_ch, new_org.name_en)
                    elif serial[13:15] != "00":
                        continue
                #res.add(PaperOrgSelectItem(serial, new_org.name_ch, new_org.name_en))
                    dict_res[serial] = PaperOrgSelectItem(serial, new_org.name_ch, new_org.name_en)

        for select_org in self.orgs_selected_list:
            serial = select_org.org_serial
            if serial[13:15] == "00": 
                if serial[9:11] == "00": # TTTTTTTTT000000
                    org_2nd_filter = f"{serial[:9]}%%0000"
                    select_org.org_serial = f"{serial[:9]}%"
                    new_org2_list = self.get_new_org2_list(org_2nd_filter, 0)
                    for new_org in new_org2_list:
                        #res.add(PaperOrgSelectItem(f"{new_org.org_serial[:11]}%", new_org.name_ch, new_org.name_en))
                        new_org_serial = f"{new_org.org_serial[:11]}%"
                        dict_res[new_org_serial] = PaperOrgSelectItem(new_org_serial, new_org.name_ch, new_org.name_en)
                elif serial[11:13] == "00": #TTTTTTTTTXX0000
                    org_2nd_filter = f"{serial[:11]}%"
                    select_org.org_serial = f"{serial[:11]}%"
                    new_org2_list = self.get_new_org2_list(org_2nd_filter, 0)
                    new_add_ret(dict_res, new_org2_list)
                else: #TTTTTTTTTXXXX00
                    org_2nd_filter = f"{serial[:13]}%"
                    select_org.org_serial = f"{serial[:13]}%"
                    new_org2_list = self.get_new_org2_list(org_2nd_filter, 0)
                    new_add_ret(dict_res, new_org2_list)

                dict_res[serial] = PaperOrgSelectItem(serial, select_org.name_ch, select_org.name_en)
            elif serial[11:15] == "7999":  # 台大醫學院總計(額外處理)    
                org_2nd_filter = serial[:12]
                select_org.org_serial = f"{serial[:12]}%"
                new_org2_list = self.get_new_org2_list(org_2nd_filter, 1)
                new_add_ret(dict_res, new_org2_list)

            dict_res[select_org.org_serial] = PaperOrgSelectItem(select_org.org_serial, select_org.name_ch, select_org.name_en)
        res.items = list(dict_res.values())
        print(f"refresh 過後的機構數量: {len(res.items)}")
        return res

    def refresh_orgs(self)-> PaperOrgSelectedValue:
        res = PaperOrgSelectedValue()
        dict_res = {}
        org_2nd_filter : str|None = None
        item_list : list[list[str]] = []

        #def add_ret(res : PaperOrgSelectedValue, org_list:list[PaperOrg], org_23nd_check : bool = True):
        def add_ret(dict_res : dict[str, PaperOrgSelectItem], org_list:list[PaperOrg], org_23nd_check : bool = True):
            for new_org in org_list:
                serial_13_str = new_org.org_serial[0:13]
                serial = new_org.org_serial
                if org_23nd_check:
                    exist = [x for x in org_list if x.org_serial.startswith(serial_13_str) and x.org_serial != serial]
                    if serial[11:13] != "00" and serial[13:15] == "00":
                        if len(exist) > 0:
                            incorporate_serial = f"{serial_13_str}%"
                            dict_res[incorporate_serial] = PaperOrgSelectItem(incorporate_serial, new_org.name_ch, new_org.name_en)
                    elif serial[13:15] != "00":
                        continue
                #res.add(PaperOrgSelectItem(serial, new_org.name_ch, new_org.name_en))
                    dict_res[serial] = PaperOrgSelectItem(serial, new_org.name_ch, new_org.name_en)

        #skip_add = False
        for select_org in self.orgs_selected_list:
            serial = select_org.org_serial
            if len(serial) == 15 :
                if serial[13:15] == "00":
                    if serial[9:11] == "00":
                        item_list.append(["1", serial])
                        org_2nd_filter = f"{serial[:9]}%%0000"
                        select_org.org_serial = f"{serial[:9]}%"
                        new_org2_list = self.get_new_org2_list(org_2nd_filter, 0)
                        for new_org in new_org2_list:
                            #res.add(PaperOrgSelectItem(f"{new_org.org_serial[:11]}%", new_org.name_ch, new_org.name_en))
                            new_org_serial = f"{new_org.org_serial[:11]}%"
                            dict_res[new_org_serial] = PaperOrgSelectItem(new_org_serial, new_org.name_ch, new_org.name_en)
                    else:
                        if serial[11:13] == "00":
                            item_list.append(["2", serial])
                            if not self.check_upper_org(item_list, serial, 1):
                                org_2nd_filter = f"{serial[:11]}"
                                select_org.org_serial = f"{serial[:11]}%"
                            else:
                                print(f"被跳過的ID : {serial}")
                                continue
                        else:
                            item_list.append(["3", serial])
                            if not self.check_upper_org(item_list, serial, 2):
                                org_2nd_filter = f"{serial[:13]}%"
                                select_org.org_serial = f"{serial[:13]}%"
                                #skip_add = True
                            else:
                                print(f"被跳過的ID : {serial}")
                                continue
                        new_org2_list = self.get_new_org2_list(org_2nd_filter, 0)
                        #add_ret(res, new_org2_list)
                        add_ret(dict_res, new_org2_list)

                elif serial[11:15] == "7999":  # 台大醫學院總計(額外處理)    
                    item_list.append(["2", serial])
                    org_2nd_filter = serial[:12]
                    select_org.org_serial = f"{serial[:12]}%"
                    new_org2_list = self.get_new_org2_list(org_2nd_filter, 1)
                    #add_ret(res, new_org2_list)
                    add_ret(dict_res, new_org2_list)

            dict_res[select_org.org_serial] = PaperOrgSelectItem(select_org.org_serial, select_org.name_ch, select_org.name_en)
            # if not skip_add :
            #     dict_res[select_org.org_serial] = PaperOrgSelectItem(select_org.org_serial, select_org.name_ch, select_org.name_en)
            # skip_add = False
            
        res.items = list(dict_res.values())
        print(f"refresh 過後的機構數量: {len(res.items)}")
        return res

    def check_upper_org(self, item_list:list[list[str]], serial:str, org_level:int):
        length = 0 
        if org_level ==1 :
            length = 9
        elif org_level == 2:
            length = 11
        elif org_level == 3:
            length = 13

        if length > 0 and any(x[0] == str(org_level) and x[1][:length] == serial[:length] for x in item_list):
            return True
        
        return False
        
    def get_subject(self, selected_values: list[str] | PaperOrgSelectedValue, author_index: AuthorIndex = AuthorIndex.NotLimited) -> tuple["Subject", dict[str, "Column"],Any, str, str]:
        from dal_provider import get_dal
        dal = get_dal()
        if not self.orgs_selected_list:
            self._fetch_all_orgs(selected_values)

        if isinstance(selected_values, list) :
            final_select_orgs = self.new_refresh_orgs()
        elif isinstance(selected_values, PaperOrgSelectedValue) :
            final_select_orgs = selected_values

        final_select_orgs.author_index = author_index # 暫時不更動下面邏輯，如果author_index真的不需要特別存 再移除

        orgs = final_select_orgs.items

        tblMain =dal.create_extra_column_table(db_schema.schema.Org1stTableName)
        tblMain.SetExtraColumnDef("OrgDesc", "nvarchar(1600)")
        colBind = tblMain.RetrieveColumn(db_schema.schema.MainBindColumnName)
        colAddrIdx = tblMain.RetrieveColumn(db_schema.schema.AddrIndexColumnName)
        colRp = tblMain.RetrieveColumn(db_schema.schema.ReprintColumnName)

        tblOrg = dal.create_table(db_schema.schema.Org1stTableName)
        colOrgBind = tblOrg.RetrieveColumn(db_schema.schema.MainBindColumnName)
        colOrgAddrIdx = tblOrg.RetrieveColumn(db_schema.schema.AddrIndexColumnName)
        colOrgReprint = tblOrg.RetrieveColumn(db_schema.schema.ReprintColumnName)
        colOrgSerial = tblOrg.RetrieveColumn(db_schema.schema.OrgColumnName)

        tblAOR = dal.create_table(db_schema.schema.WOSAuthorOrgRelationTableName)
        colAORBind = tblAOR.RetrieveColumn(db_schema.schema.MainBindColumnName)
        colAORAuthorIdx = tblAOR.RetrieveColumn(db_schema.schema.AuthorIndexColumnName)
        colAORAddrIdx = tblAOR.RetrieveColumn(db_schema.schema.AddrIndexColumnName)
        colAORReprint = tblAOR.RetrieveColumn(db_schema.schema.ReprintColumnName)

        on = dal.create_join_on()
        on.Add(colOrgBind, colAORBind)
        on.Add(colOrgAddrIdx, colAORAddrIdx)
        on.Add(colOrgReprint, colAORReprint)

        jtb = dal.create_join_table(tblOrg, tblAOR, dal.JOINTYPE.InnerJoin, on)
        ret = dal.create_subject(tblMain, tblMain.ShownColumn)

        ret.Initialize()
        for org in orgs:
            for org_item in org.items:
                restrict_org = None
                if isinstance(org_item, PaperOrg2ndItem):
                    tblOrg.SetFullName(db_schema.schema.Org2ndTableName)
                    restrict_org = dal.create_where_column_to_const(colOrgSerial, dal.OPTYPE.Like, org_item.query_var)
                    if org_item.query_var == "TWU000001100000":
                        restrict_org2 = dal.create_where_column_to_const(colOrgSerial, dal.OPTYPE.Like, "TWU000001110000")
                        restrict_org = dal.create_where_multiple([restrict_org, restrict_org2], dal.OPTYPE.Or)
                    elif org_item.query_var == "TWU00000110%":
                        restrict_org2 = dal.create_where_column_to_const(colOrgSerial, dal.OPTYPE.Like, "TWU00000111%")
                        restrict_org = dal.create_where_multiple([restrict_org, restrict_org2], dal.OPTYPE.Or)
                    elif org_item.query_var == "TWU000001120000":
                        restrict_org2 = dal.create_where_column_to_const(colOrgSerial, dal.OPTYPE.Like, "TWU000001130000")
                        restrict_org = dal.create_where_multiple([restrict_org, restrict_org2], dal.OPTYPE.Or)
                        restrict_org3 = dal.create_where_column_to_const(colOrgSerial, dal.OPTYPE.Like, "TWU000001140000")
                        restrict_org = dal.create_where_multiple([restrict_org, restrict_org3], dal.OPTYPE.Or)
                    elif org_item.query_var == "TWU00000112%":
                        restrict_org2 = dal.create_where_column_to_const(colOrgSerial, dal.OPTYPE.Like, "TWU00000113%")
                        restrict_org = dal.create_where_multiple([restrict_org, restrict_org2], dal.OPTYPE.Or)
                        restrict_org3 = dal.create_where_column_to_const(colOrgSerial, dal.OPTYPE.Like, "TWU00000114%")
                        restrict_org = dal.create_where_multiple([restrict_org, restrict_org3], dal.OPTYPE.Or)
                    
                    pass
                else:
                    tblOrg.SetFullName(db_schema.schema.Org1stTableName)
                    restrict_org = dal.create_where_column_to_const(colOrgSerial, dal.OPTYPE.Equal, org_item.serial)

                author_idx_restrict = None

                if final_select_orgs.author_index == AuthorIndex.FirstAuthor:
                    author_idx_restrict = dal.create_where_column_to_const(colAORAuthorIdx,dal.OPTYPE.Equal,"1")
                elif final_select_orgs.author_index == AuthorIndex.Reprint:
                    author_idx_restrict = dal.create_where_column_to_const(colAORReprint,dal.OPTYPE.Equal,"1")
                elif final_select_orgs.author_index == AuthorIndex.FirstOrReprint:
                    author_idx_restrict1 = dal.create_where_column_to_const(colAORAuthorIdx,dal.OPTYPE.Equal,"1")
                    author_idx_restrict2 = dal.create_where_column_to_const(colAORReprint,dal.OPTYPE.Equal,"1")
                    author_idx_restrict = dal.create_where_multiple([author_idx_restrict1, author_idx_restrict2],dal.OPTYPE.Or)
                if author_idx_restrict:
                    restrict_org= dal.create_where_multiple([restrict_org, author_idx_restrict],dal.OPTYPE.And)
                query = dal.create_where_column_val_in_join_table_column_multiple([colBind, colAddrIdx, colRp ],[ colOrgBind, colOrgAddrIdx, colOrgReprint ], jtb, restrict_org)
                ret.Add(self.get_org_name(org).replace("'", "''"), [ query ])

        return  ret, {db_schema.schema.MainBindColumnName: colBind,  db_schema.schema.AddrIndexColumnName:colAddrIdx , db_schema.schema.ReprintColumnName: colRp },final_select_orgs, "機構", "Organization"
        

    @staticmethod
    def get_org_name(org:PaperOrgSelectItem) -> str:
        #return org.raw_serial + "-" + org.org_name
        # PresidentReportOrgSubjectInfo
        return f"{org.raw_serial}\x1c{org.org_name_ch}\x1c{org.org_name_en}"


