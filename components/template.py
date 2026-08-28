## PRISAnalyzer.PresidentReportESI.Class.Analysis.Templates.Template
from dataclasses import dataclass, field
from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.utils import get_column_letter
from abc import ABC, abstractmethod

# PRIS
from export.excel_report import *


# 每一個sheet的資料
@dataclass
class Template(ABC):
    sheet_name : str
    main_ver : str
    comp_ver : str
    sheet_idx : int
    sheet_name_proj : str = ""
    #_sheet_tab_name : str = ""
    _excel_func: dict[int, str] = field(default_factory=dict) 
    rows : list[list[str]] = field(default_factory=list)
    null_val_loc : set[str] = field(default_factory=set)
    dummyColsWithoutFormt : set[int] = field(default_factory=set)
    DefaultExcelFuncInteger : str = "=TEXT({0}, \"##,#0\")"
    DefaultExcelFuncPercent : str = "=TEXT({0}, \"0.00%\")"
    DefaultExcelFunc2DecimalPlace : str = "=TEXT({0}, \"0.00\")"
    DefaultExcelFuncProgress : str = "=TEXT({0}, \"+##,#0;-##,#0;##,0\")"
    RawdataSheetSuffix :str = "rawdata"

    @property
    def sheet_tab_name(self) -> str:
        return f"sheet{self.sheet_idx}"

    @property
    def rawdata_tab_name(self) -> str:
        return f"{self.sheet_tab_name}_{self.RawdataSheetSuffix}"
    
    @property
    def ColsWithoutFormat(self) -> set[int]:
        return self.dummyColsWithoutFormt

    @property
    def DefaultCellHorizontalAlignment(self) -> str:
        return "center"
    @property
    def DefaultCellVerticalAlignment(self) -> str:
        return "center"

    @abstractmethod
    def get_report(self) -> ExcelReport:
        pass

    def to_worksheet(self, wb : Workbook, rows: list[list[str]] ):
        self.rows = rows
        self.rawdata_to_worksheet(wb, rows)

        report = self.get_report()
        report_rows : list[list[ECell]] = []
        for idx, rr in enumerate(rows):
            rcells = self.get_cell_row(idx+1, rr)
            report_rows.append(rcells)

        report.rows = report_rows
        report.export(wb, self.sheet_tab_name)   
        

    def get_cell_row(self, r:int, row : list[str]) -> list[ECell] :
        r_cells = []
        c = 1
        for col in row:
            if c in self.ColsWithoutFormat:
                r_cells.append(
                    ECell(
                        text=col, 
                        vertical_align=self.DefaultCellVerticalAlignment,
                        horizontal_align=self.DefaultCellHorizontalAlignment,
                        is_formula= False
                    )
                )
            else:
                r_cells.append(
                    ECell(
                        text=self.get_cell_value(r,c), 
                        vertical_align=self.DefaultCellVerticalAlignment,
                        horizontal_align=self.DefaultCellHorizontalAlignment,
                        is_formula= True
                    )
                )
            c+=1
        return r_cells

    def get_cell_value(self,r : int, c:int) -> str:
        cell_loc_str = self.get_cell_loc_str(r,c)
        check_str = f"{r},{c}"
        if check_str in self.null_val_loc:
            return ""
        if c in self._excel_func:
            return self._excel_func[c].format(cell_loc_str)
        else:
            return f"={cell_loc_str}"

    def get_cell_loc_str(self,r : int, c:int) -> str:
        return f"'{self.rawdata_tab_name}'!{self.get_cell_letter(r,c)}"

    def get_cell_letter(self,r : int, c:int) -> str:
        return f"{get_column_letter(c)}{r}"

    def rawdata_to_worksheet(self, wb : Workbook, rows: list[list[str]] ):
        # 為了辨別ws是Worksheet加了: Worksheet
        ws :Worksheet = wb.create_sheet(self.rawdata_tab_name) 
        r = 1
        for row in rows:
            c = 1
            for col in row:
                cell = ws.cell(r,c)
                cell.value = col
                if not col:
                    self.null_val_loc.add(f"{r},{c}")
                c += 1
            r+=1

class E1(Template):
    def __init__(self, sheet_name: str, main_ver: str, comp_ver: str, sheet_index: int):
        super().__init__(sheet_name, main_ver, comp_ver, sheet_index)  # 對應 : base(...)

        self._excel_func: dict[int, str] = {
            5: Template.DefaultExcelFuncInteger,
            6: Template.DefaultExcelFuncInteger,
            7: Template.DefaultExcelFuncInteger,
            8: Template.DefaultExcelFuncInteger,
            9: Template.DefaultExcelFuncInteger,
            10: Template.DefaultExcelFuncInteger,
            11: Template.DefaultExcelFuncProgress,
            12: Template.DefaultExcelFuncProgress,
        }
        self._cols_without_format: set[int] = {1, 2, 3, 4}
        
    @property
    def excel_func(self) -> dict[int, str]:
        return self._excel_func

    @property
    def ColsWithoutFormat(self) -> set[int]:
        return self._cols_without_format

    @property
    def val_col_header_name(self) -> str:
        return "論文篇數"
    
    def get_report(self) -> ExcelReport:
        report = ExcelReport()
        banner=ExcelColumnHeader(name=self.sheet_name, horizontal_align="center")
        serial=ExcelColumnHeader(name="機構編號", horizontal_align= "center", merge_row_range=2, width=12)
        country=ExcelColumnHeader(name="國家", horizontal_align= "center", merge_row_range=2, width=12)
        name_ch=ExcelColumnHeader(name="學校名稱", horizontal_align= "center", merge_row_range=2, width=15)
        name_en=ExcelColumnHeader(name="學校英文名稱", horizontal_align= "center", merge_row_range=2, width=20)
        comp_ver = ExcelColumnHeader(name=self.comp_ver, horizontal_align="center")
        val_comp_ver = ExcelColumnHeader(name=self.val_col_header_name, horizontal_align="center",width=17)
        world_rank_comp_ver = ExcelColumnHeader(name="世界排名",horizontal_align="center",width=12)
        asia_pacific_rank_comp_ver = ExcelColumnHeader(name="亞太排名",horizontal_align="center",width=12)
        comp_ver.sub_headers = [val_comp_ver, world_rank_comp_ver, asia_pacific_rank_comp_ver]

        main_ver = ExcelColumnHeader(name=self.main_ver,horizontal_align="center")
        val_main_ver = ExcelColumnHeader(name=self.val_col_header_name,horizontal_align="center",width=17)
        world_rank_main_ver = ExcelColumnHeader(name="世界排名",horizontal_align="center",width=12)
        asia_pacific_rank_main_ver = ExcelColumnHeader(name="亞太排名",horizontal_align="center",width=12)
        main_ver.sub_headers = [val_main_ver, world_rank_main_ver, asia_pacific_rank_main_ver]

        world_prog = ExcelColumnHeader(name="世界排名進退步",horizontal_align="center",merge_row_range=2,width=18)
        asia_pacific_prog = ExcelColumnHeader(name="亞太排名進退步",horizontal_align="center",merge_row_range=2,width=18)

        banner.sub_headers = [serial, country, name_ch, name_en, comp_ver, main_ver, world_prog, asia_pacific_prog]
        report.headers = [banner]
        return report

class E2(E1):
    def __init__(self, sheet_name: str, main_ver: str, comp_ver: str, sheet_index: int):
        super().__init__(sheet_name, main_ver, comp_ver, sheet_index)  

    @property
    def val_col_header_name(self) -> str:
        return "被引次數"


class E3(Template):
    def __init__(self, sheet_name: str, main_ver: str, comp_ver: str, sheet_index: int):
        super().__init__(sheet_name, main_ver, comp_ver, sheet_index)  # 對應 : base(...)
        self.defaultExcelFunc = "=TEXT({0}, \"0.00\")"
        self._excel_func: dict[int, str] = {
            5: self.defaultExcelFunc,
            6: Template.DefaultExcelFuncInteger,
            7: self.defaultExcelFunc,
            8: Template.DefaultExcelFuncInteger,
            9: Template.DefaultExcelFuncProgress
        }
        self._cols_without_format: set[int] = {1, 2, 3, 4}
        
    @property
    def excel_func(self) -> dict[int, str]:
        return self._excel_func

    @property
    def ColsWithoutFormat(self) -> set[int]:
        return self._cols_without_format

    @property
    def val_col_header_name(self) -> str:
        return "平均被引次數"
    
    def get_report(self) -> ExcelReport:
        report = ExcelReport()
        banner=ExcelColumnHeader(name=self.sheet_name, horizontal_align="center")
        serial=ExcelColumnHeader(name="機構編號", horizontal_align= "center", merge_row_range=2, width=12)
        country=ExcelColumnHeader(name="國家", horizontal_align= "center", merge_row_range=2, width=12)
        name_ch=ExcelColumnHeader(name="學校名稱", horizontal_align= "center", merge_row_range=2, width=15)
        name_en=ExcelColumnHeader(name="學校英文名稱", horizontal_align= "center", merge_row_range=2, width=20)
        comp_ver = ExcelColumnHeader(name=self.comp_ver, horizontal_align="center")
        val_comp_ver = ExcelColumnHeader(name=self.val_col_header_name, horizontal_align="center",width=18)
        rank_comp_ver = ExcelColumnHeader(name="相對排名", horizontal_align="center",width=12)
        comp_ver.sub_headers = [val_comp_ver, rank_comp_ver]
        main_ver = ExcelColumnHeader(name=self.main_ver,horizontal_align="center")
        val_main_ver = ExcelColumnHeader(name=self.val_col_header_name,horizontal_align="center",width=18)
        rank_main_ver = ExcelColumnHeader(name="相對排名", horizontal_align="center",width=12)
        main_ver.sub_headers = [val_main_ver, rank_main_ver]
        prog = ExcelColumnHeader(name="名次進退步", horizontal_align="center",merge_row_range = 2, width=18)

        banner.sub_headers = [serial, country, name_ch, name_en, comp_ver, main_ver, prog]
        report.headers = [banner]
        return report

class E4(Template):
    def __init__(self, sheet_name: str, main_ver: str, comp_ver: str, sheet_index: int):
        super().__init__(sheet_name, main_ver, comp_ver, sheet_index)  # 對應 : base(...)
        self.excel_func3 = "=TEXT({0},\"+0.00%;-0.00%;0.00%\")"
        self._excel_func: dict[int, str] = {
            5: Template.DefaultExcelFuncInteger,
            6: Template.DefaultExcelFuncInteger,
            7: Template.DefaultExcelFuncPercent,
            8: Template.DefaultExcelFuncInteger,
            9: Template.DefaultExcelFuncInteger,
            10:Template.DefaultExcelFuncPercent,
            11:self.excel_func3
        }
        self._cols_without_format: set[int] = {1, 2, 3, 4}
        
    @property
    def excel_func(self) -> dict[int, str]:
        return self._excel_func

    @property
    def ColsWithoutFormat(self) -> set[int]:
        return self._cols_without_format

    @property
    def pc_col_header_name(self) -> str:
        return "論文總數"
    @property
    def hici_col_header_name(self) -> str:
        return "高被引論文數"
    @property
    def hici_ratio_col_header_name(self) -> str:
        return "高被引論文比率"
    
    def get_report(self) -> ExcelReport:
        report = ExcelReport()
        banner=ExcelColumnHeader(name=self.sheet_name, horizontal_align="center")
        serial=ExcelColumnHeader(name="機構編號", horizontal_align= "center", merge_row_range=2, width=12)
        country=ExcelColumnHeader(name="國家", horizontal_align= "center", merge_row_range=2, width=12)
        name_ch=ExcelColumnHeader(name="學校名稱", horizontal_align= "center", merge_row_range=2, width=15)
        name_en=ExcelColumnHeader(name="學校英文名稱", horizontal_align= "center", merge_row_range=2, width=20)
        comp_ver = ExcelColumnHeader(name=self.comp_ver, horizontal_align="center")
        paper_count_comp_ver = ExcelColumnHeader(name=self.pc_col_header_name, horizontal_align="center",width=15)
        hici_comp_ver =  ExcelColumnHeader(name=self.hici_col_header_name, horizontal_align="center",width=15)
        hici_ratio_comp_ver =  ExcelColumnHeader(name=self.hici_ratio_col_header_name, horizontal_align="center",width=18)
        comp_ver.sub_headers = [paper_count_comp_ver, hici_comp_ver, hici_ratio_comp_ver]

        main_ver = ExcelColumnHeader(name=self.main_ver,horizontal_align="center")
        paper_count_main_ver = ExcelColumnHeader(name=self.pc_col_header_name, horizontal_align="center",width=15)
        hici_main_ver =  ExcelColumnHeader(name=self.hici_col_header_name, horizontal_align="center",width=15)
        hici_ratio_main_ver =  ExcelColumnHeader(name=self.hici_ratio_col_header_name, horizontal_align="center",width=18)
        main_ver.sub_headers = [paper_count_main_ver, hici_main_ver, hici_ratio_main_ver]
        hici_growth_rate = ExcelColumnHeader(name="高被引論文數成長率", horizontal_align="center",merge_row_range = 2, width=22)

        banner.sub_headers = [serial, country, name_ch, name_en, comp_ver, main_ver, hici_growth_rate]
        report.headers = [banner]
        return report


class E5(Template):
    def __init__(self, sheet_name: str, main_ver: str, comp_ver: str, sheet_index: int):
        super().__init__(sheet_name, main_ver, comp_ver, sheet_index)  # 對應 : base(...)
        self._excel_func: dict[int, str] = {
            5: Template.DefaultExcelFuncInteger,
            6: Template.DefaultExcelFuncInteger,

        }
        self._cols_without_format: set[int] = {1, 2, 3, 4}
        
    @property
    def excel_func(self) -> dict[int, str]:
        return self._excel_func

    @property
    def ColsWithoutFormat(self) -> set[int]:
        return self._cols_without_format
    
    def get_report(self) -> ExcelReport:
        report = ExcelReport()
        banner=ExcelColumnHeader(name=self.sheet_name, horizontal_align="center")
        serial=ExcelColumnHeader(name="機構編號", horizontal_align= "center", width=12)
        country=ExcelColumnHeader(name="國家", horizontal_align= "center", width=12)
        name_ch=ExcelColumnHeader(name="學校名稱", horizontal_align= "center", width=15)
        name_en=ExcelColumnHeader(name="學校英文名稱", horizontal_align= "center", width=20)
        comp_ver = ExcelColumnHeader(name=self.comp_ver, horizontal_align="center", width=28)
        main_ver = ExcelColumnHeader(name=self.main_ver,horizontal_align="center", width=28)
       
        banner.sub_headers = [serial, country, name_ch, name_en, comp_ver, main_ver]
        report.headers = [banner]
        return report
    
class E6(Template):
    def __init__(self, sheet_name: str, fields:list[tuple[str,list[str]]], sheet_index: int):
        super().__init__(sheet_name, "", "", sheet_index)  # 對應 : base(...)
        self.fields = fields
        
    @property
    def excel_func(self) -> dict[int, str]:
        return None

    @property
    def val_col_header_name(self) -> str:
        return "論文篇數"
        
    def get_report(self) -> ExcelReport:
        report = ExcelReport()
        banner=ExcelColumnHeader(name=self.sheet_name, horizontal_align="center")
        serial=ExcelColumnHeader(name="機構編號", horizontal_align= "center", merge_row_range=3, width=12)
        country=ExcelColumnHeader(name="國家", horizontal_align= "center", merge_row_range=3, width=12)
        name_ch=ExcelColumnHeader(name="學校名稱", horizontal_align= "center", merge_row_range=3, width=15)
        name_en=ExcelColumnHeader(name="學校英文名稱", horizontal_align= "center", merge_row_range=3, width=18)
        banner.sub_headers = [serial, country, name_ch, name_en]

        for main_field, sub_fields in self.fields:
            field_col = ExcelColumnHeader(name=main_field, horizontal_align= "center")
            for sub_field in sub_fields:
                sub_field_col = ExcelColumnHeader(name = sub_field, horizontal_align= "center")
                val_col = ExcelColumnHeader(name =self.val_col_header_name, horizontal_align="center", width=12)
                world_prog = ExcelColumnHeader(name ="世界排名", horizontal_align="center", width=12)
                asia_pacific_prog = ExcelColumnHeader(name ="亞太排名", horizontal_align="center", width=12)
                sub_field_col.sub_headers = [val_col, world_prog,asia_pacific_prog]
                field_col.sub_headers.append(sub_field_col)
            banner.sub_headers.append(field_col)

        report.headers = [banner]
        return report
       
    
    # overwrite
    def get_cell_row(self, r:int, row : list[str]) -> list[ECell] :
        r_cells = []
        end =  ((len(row) - 4) // 5) * 3 + 4
        for c in range(1, end):
            if c <= 4:
                r_cells.append(ECell(
                    text=row[c-1],
                    vertical_align=self.DefaultCellVerticalAlignment, 
                    horizontal_align=self.DefaultCellHorizontalAlignment, 
                    is_formula=False
                ))
            else:
                offset_C = c-4
                ori_c = (offset_C // 3) * 5 + 5 if (offset_C % 3 == 1) else ((offset_C // 3) * 5 + 6 if (offset_C % 3 == 2) else (offset_C // 3) * 5 + 3)
                if f"{r},{ori_c}" in self.null_val_loc:
                    r_cells.append(ECell(text=""))
                    continue
                if (c-4)%3 == 1:
                    r_cells.append(ECell(
                        text=self.DefaultExcelFuncInteger.format(self.get_cell_loc_str(r,ori_c)), 
                        vertical_align=self.DefaultCellVerticalAlignment, 
                        horizontal_align=self.DefaultCellHorizontalAlignment, 
                        is_formula=True
                    ))
                else:
                    if f"{r},{ori_c+1}" in self.null_val_loc:
                        r_cells.append(ECell(text=f"={self.get_cell_loc_str(r,ori_c)}", is_formula= True))
                        continue
                    str_format = "=TEXT({0}, \"#,##0\")&CHAR(10)&\"(\"&TEXT({1}, \"+#,##0;-#,##0;#,##0\")&\")\""
                    r_cells.append(ECell(
                        text=str_format.format(self.get_cell_loc_str(r,ori_c), self.get_cell_loc_str(r,ori_c+1)), 
                        vertical_align=self.DefaultCellVerticalAlignment, 
                        horizontal_align=self.DefaultCellHorizontalAlignment, 
                        is_formula=True
                    ))
                
        return r_cells

class E7(E6):
    def __init__(self, sheet_name, fields, sheet_index):
        super().__init__(sheet_name, fields, sheet_index)
    @property
    def val_col_header_name(self) -> str:
        return "被引次數"

class F1(Template):
    def __init__(self, sheet_name: str, main_ver: str, orgs:list["OrgInfo"], sheet_index: int):
        super().__init__(sheet_name, main_ver, "", sheet_index)  # 對應 : base(...)
        self.orgs = orgs
        
    @property
    def excel_func(self) -> dict[int, str]:
        return None

    @property
    def RankingType(self) -> str:
        return "世界排名"

    def create_org_header_tree(self,org: "OrgInfo") -> ExcelColumnHeader:
        bottom_headers = [
            ExcelColumnHeader(name="論文篇數",width=12),
            ExcelColumnHeader(name=self.RankingType, width=10),
            ExcelColumnHeader(name="排名變化", width=10)
        ]
        org_en_header = ExcelColumnHeader(name = org.org_name_en,wrap_text=True, max_char=29,height_per_row=17.75,sub_headers=bottom_headers)
        org_ch_header = ExcelColumnHeader(name = org.org_name_ch,wrap_text=True, max_char=29,height_per_row=17.75,sub_headers=[org_en_header])
        country_header = ExcelColumnHeader(name = org.country,sub_headers=[org_ch_header])
        top_header = ExcelColumnHeader(name = org.org_serial,sub_headers=[country_header])

        return top_header

    def create_first_header_tree(self) -> ExcelColumnHeader:
        bottom_headers = ExcelColumnHeader(name = "領域",height=30)
        org_en_header = ExcelColumnHeader(name = "學校英文名稱",sub_headers=[bottom_headers])
        org_ch_header = ExcelColumnHeader(name = "學校名稱",sub_headers=[org_en_header])
        country_header = ExcelColumnHeader(name = "國家",sub_headers=[org_ch_header])
        top_header = ExcelColumnHeader(name = "機構編號",sub_headers=[country_header],width=34)
        
        return top_header
    
        
    def get_report(self) -> ExcelReport:
        report = ExcelReport()
        banner=ExcelColumnHeader(name=self.sheet_name)
        org_headers = [self.create_org_header_tree(x) for x in self.orgs]
        first_header =  self.create_first_header_tree()
        
        banner.sub_headers = [first_header] + org_headers
        report.headers = [banner]
        return report
    
    # overwrite
    def get_cell_row(self, r:int, row : list[str]) -> list[ECell] :
        if len(row) == 1 :
            return self.get_field_cell_row(r, row)
        elif r == len(self.rows):
            return self.get_enter_esi_cell_row(r, row)
        else:
            return self.get_sub_field_cell_row(r, row)
        
    # new
    def get_field_cell_row(self, r:int, row : list[str]) -> list[ECell] :
        # XLColor.FromArgb(217, 217, 217) = "D9D9D9"
        return [ECell(text=row[0], merge_col_range=(len(self.orgs)*3)+1, bg_color="D9D9D9")]

    # new
    def get_enter_esi_cell_row(self, r:int, row : list[str]) -> list[ECell] :
        r_cells =[]
        c = 1
        for col in row:
            if c==1:
                r_cells.append(ECell(text="進入ESI排行領域數", bold=True))
            r_cells.append(ECell(text=col, bold=True,merge_col_range=3))
            r_cells.append(ECell(text=""))
            r_cells.append(ECell(text=""))

            c+=1
        return r_cells

    # new
    def get_sub_field_cell_row(self, r:int, row : list[str]) -> list[ECell] :
        r_cells =[]
        c = 1
        for col in row:
            if f"{r},{c}" in self.null_val_loc:
                r_cells.append(ECell(text=""))
            elif c == 1:
                r_cells.append(ECell(text=col))
            elif ((c - 1) % 3 == 1) or ((c - 1) % 3 == 2):
                r_cells.append(ECell(text=self.DefaultExcelFuncInteger.format(self.get_cell_loc_str(r,c)), is_formula=True))
            else:
                r_cells.append(ECell(text=self.DefaultExcelFuncProgress.format(self.get_cell_loc_str(r,c)), is_formula=True))
            c+=1
        return r_cells

class F2(F1):
    def __init__(self, sheet_name: str, main_ver: str, orgs:list["OrgInfo"], sheet_index: int):
        super().__init__(sheet_name, main_ver, orgs, sheet_index)  # 對應 : base(...)

    @property
    def RankingType(self) -> str:
        return "亞太排名"

class F3(Template):
    def __init__(self, sheet_name: str, main_ver: str, orgs:list["OrgInfo"], sheet_index: int):
        super().__init__(sheet_name, main_ver, "", sheet_index)  # 對應 : base(...)
        self.orgs = orgs
        
    @property
    def excel_func(self) -> dict[int, str]:
        return None

    @property
    def RankingType(self) -> str:
        return "世界排名"
    
    @property
    def rows_count(self) -> int:
        return len(self.rows)

    def create_org_header_tree(self,org: "OrgInfo") -> ExcelColumnHeader:
        bottom_headers = [
            ExcelColumnHeader(name="被引次數",width=15),
            ExcelColumnHeader(name=self.RankingType, width=10),
            ExcelColumnHeader(name="排名變化", width=10),
            ExcelColumnHeader(name="平均被引", width=10)
        ]
        org_en_header = ExcelColumnHeader(name = org.org_name_en,wrap_text=True, max_char=38,height_per_row=17.75,sub_headers=bottom_headers)
        org_ch_header = ExcelColumnHeader(name = org.org_name_ch,wrap_text=True, max_char=38,height_per_row=17.75,sub_headers=[org_en_header])
        country_header = ExcelColumnHeader(name = org.country,sub_headers=[org_ch_header])
        top_header = ExcelColumnHeader(name = org.org_serial,sub_headers=[country_header])

        return top_header

    def create_first_header_tree(self) -> ExcelColumnHeader:
        bottom_headers = ExcelColumnHeader(name = "領域")
        org_en_header = ExcelColumnHeader(name = "學校英文名稱",sub_headers=[bottom_headers])
        org_ch_header = ExcelColumnHeader(name = "學校名稱",sub_headers=[org_en_header])
        country_header = ExcelColumnHeader(name = "國家",sub_headers=[org_ch_header])
        top_header = ExcelColumnHeader(name = "機構編號",sub_headers=[country_header],width=34)
        
        return top_header
    def get_report(self) -> ExcelReport:
        report = ExcelReport()
        banner=ExcelColumnHeader(name=self.sheet_name)
        org_headers = [self.create_org_header_tree(x) for x in self.orgs]
        first_header =  self.create_first_header_tree()

        second_column = ExcelColumnHeader(name = "=\"門\"&CHAR(10)&CHAR(10)&\"檻\"&CHAR(10)&CHAR(10)&\"值\"", width=12, wrap_text=True, merge_row_range=5, is_formula=True)
        third_column = ExcelColumnHeader(name = "=\"世\"&CHAR(10)&\"界\"&CHAR(10)&\"平\"&CHAR(10)&\"均\"&CHAR(10)&\"被\"&CHAR(10)&\"引\"", width=12, wrap_text=True, merge_row_range=5, is_formula=True)
        
        banner.sub_headers = [first_header,second_column,third_column] + org_headers
        report.headers = [banner]
        return report

    
    # overwrite
    def get_cell_row(self, r:int, row : list[str]) -> list[ECell] :
        if len(row) == 1 :
            return self.get_field_cell_row(r, row)
        elif r == self.rows_count-1:
            return self.get_enter_maj_field_cell_row(r, row)
        elif r == self.rows_count:
            return self.get_enter_esi_cell_row(r, row)
        else:
            return self.get_sub_field_cell_row(r, row)
        
    # F3 new
    def get_field_cell_row(self, r:int, row : list[str]) -> list[ECell] :
        # XLColor.FromArgb(217, 217, 217) = "D9D9D9"
        return [ECell(text=row[0], merge_col_range=(len(self.orgs)*4)+3, bg_color="D9D9D9")]

    # F3 new
    def get_enter_esi_cell_row(self, r:int, row : list[str]) -> list[ECell] :
        r_cells =[]
        c = 1
        for col in row:
            if c==1:
                r_cells.append(ECell(text="進入排行領域數(ESI領域)", bold=True, merge_col_range=3))
                r_cells.append(ECell(text=""))
                r_cells.append(ECell(text=""))

            r_cells.append(ECell(text=col, bold=True, merge_col_range=4))
            r_cells.append(ECell(text=""))
            r_cells.append(ECell(text=""))
            r_cells.append(ECell(text=""))

            c+=1
        return r_cells

    # new
    def get_sub_field_cell_row(self, r:int, row : list[str]) -> list[ECell] :
        r_cells =[]
        c = 1
        for col in row:
            if f"{r},{c}" in self.null_val_loc:
                r_cells.append(ECell(text=""))
            elif c == 1:
                r_cells.append(ECell(text=col))
            elif (c == 2 or (c - 3) % 4 == 1) or ((c - 3) % 4 == 2):
                r_cells.append(ECell(text=self.DefaultExcelFuncInteger.format(self.get_cell_loc_str(r,c)), is_formula=True))
            elif ((c-3) % 4 == 3):
                r_cells.append(ECell(text=self.DefaultExcelFuncInteger.format(self.get_cell_loc_str(r,c)), is_formula=True))
            else:
                r_cells.append(ECell(text=self.DefaultExcelFunc2DecimalPlace.format(self.get_cell_loc_str(r,c)), is_formula=True))
            c+=1
        return r_cells

    def get_enter_maj_field_cell_row(self, r:int, row : list[str]) -> list[ECell] :
        r_cells =[]
        c = 1
        for col in row:
            if c == 1:
                r_cells.append(ECell(text=f"進入排行領域數({col}大類)", bold=True, merge_col_range= 3))
            else:
                r_cells.append(ECell(text=col, bold=True, merge_col_range= 4))
                r_cells.append(ECell(text=""))

            r_cells.append(ECell(text=""))
            r_cells.append(ECell(text=""))

            c+=1
        return r_cells

class F4(F3):
    def __init__(self, sheet_name: str, main_ver: str, orgs:list["OrgInfo"], sheet_index: int):
        super().__init__(sheet_name, main_ver, orgs, sheet_index)  # 對應 : base(...)

    @property
    def RankingType(self) -> str:
        return "亞太排名"


class F5(Template):
    def __init__(self, sheet_name: str, sheet_index: int):
        super().__init__(sheet_name, "", "", sheet_index)  # 對應 : base(...)

        self._excel_func: dict[int, str] = {
            4: Template.DefaultExcelFuncInteger,
            5: Template.DefaultExcelFuncInteger,
            7: Template.DefaultExcelFuncInteger,
            8: Template.DefaultExcelFuncInteger,
            10: Template.DefaultExcelFuncInteger,
            11: Template.DefaultExcelFuncInteger,
        }
        self._cols_without_format: set[int] = {1, 2, 3, 6, 9}
        
    @property
    def excel_func(self) -> dict[int, str]:
        return self._excel_func

    @property
    def ColsWithoutFormat(self) -> set[int]:
        return self._cols_without_format

    @property
    def val_col_header_name(self) -> str:
        return "論文數"
    
    def get_report(self) -> ExcelReport:
        report = ExcelReport()
        banner=ExcelColumnHeader(name=self.sheet_name, horizontal_align="center")
        field =ExcelColumnHeader(name="領域", merge_row_range=2, width=15) 
        esi_field =ExcelColumnHeader(name="ESI領域", merge_row_range=2, width=33) 
        val =ExcelColumnHeader(name=self.val_col_header_name)
        first =ExcelColumnHeader(name="第一名機構",width=22)
        world_rank_1st = ExcelColumnHeader(name="世界排名",width=12)
        asia_pacific_rank_1st = ExcelColumnHeader(name="亞太排名",width=12)
        second =ExcelColumnHeader(name="第二名機構",width=22)
        world_rank_2st = ExcelColumnHeader(name="世界排名",width=12)
        asia_pacific_rank_2st = ExcelColumnHeader(name="亞太排名",width=12)
        third =ExcelColumnHeader(name="第三名機構",width=22)
        world_rank_3st = ExcelColumnHeader(name="世界排名",width=12)
        asia_pacific_rank_3st = ExcelColumnHeader(name="亞太排名",width=12)

        val.sub_headers = [
            first, world_rank_1st,asia_pacific_rank_1st, 
            second,world_rank_2st,asia_pacific_rank_2st,
            third,world_rank_3st,asia_pacific_rank_3st,
        ]
        banner.sub_headers = [field, esi_field, val]
        report.headers = [banner]
        return report

class F6(F5):
    def __init__(self, sheet_name: str, sheet_index: int):
        super().__init__(sheet_name, sheet_index)  # 對應 : base(...)

    @property
    def val_col_header_name(self) -> str:
        return "被引次數"