#config
from config import *
from components.template import Template
import common.util as Util

# PRIS
from export.excel_report import *
#
class Template_WOS(Template):
    _year_list: list[str] = []
    header_org_serial = "機構編碼"
    header_org_name_1 = "機構名稱1"
    header_org_name_2 = "機構名稱2"

    def __init__(self, sheet_name: str, sheet_index: int, tab_name :str):
        super().__init__(sheet_name, sheet_index)  # 對應 : base(...)
        self.tab_name = tab_name
        self._cols_without_format: set[int] = {}
        self.DefaultExcelFuncInteger = "=TEXT({0},\"#,##0\")"

    @property
    def cols_without_format(self) -> set[int]:
        return self._cols_without_format

    @classmethod
    def set_year_list(cls, years: list[str]):
        cls._year_list = years
        
    @classmethod
    def set_range_year_list(cls, range_years: list[str]):
        cls._year_range_list = range_years

    @classmethod
    def get_year_list(cls, is_range:bool = False) -> list[str]:
        return cls._year_list if is_range == False else cls._year_range_list 

    @classmethod
    def get_year_count(cls) -> int:
        return len(cls._year_list)

    @property
    def sheet_tab_name(self) -> str:
        return self.tab_name
    

    def get_report(self) -> ExcelReport:
        report = ExcelReport()
        banner=ExcelColumnHeader(name=self.sheet_name, horizontal_align="center")
        serial_top = ExcelColumnHeader()
        serial_top.sub_headers = [ExcelColumnHeader(name=self.header_org_serial, horizontal_align= "left", width=15)]
        serial_name1_top = ExcelColumnHeader()
        serial_name1_top.sub_headers= [ExcelColumnHeader(name=self.header_org_name_1, horizontal_align= "left", width=15)]
        serial_name2_top = ExcelColumnHeader()
        serial_name2_top.sub_headers= [ExcelColumnHeader(name=self.header_org_name_2, horizontal_align= "left", width=15)]
        years = self.get_year_list()
        years_headers = []
        for y in years :
            year_header = ExcelColumnHeader(name=int(y), horizontal_align="center", width=20)
            years_headers.append(year_header)

        banner.sub_headers = years_headers
        report.headers = [serial_top, serial_name1_top, serial_name2_top, banner]
        return report   

    def to_worksheet(self, wb, rows, basic_rows):
        self.rows = rows
        ## 建立rawdata_sheet
        self.rawdata_to_worksheet(wb, rows)

        report = self.get_report()
        report_rows : list[list[ECell]] = []
        for idx, rr in enumerate(self.rows):
            whole_row = basic_rows[idx] + rr
            rcells = self.get_cell_row(idx+1, whole_row)
            report_rows.append(rcells)

        report.rows = report_rows
        report.export(wb, self.sheet_tab_name)

    def get_cell_row(self, r:int, row : list[str]) -> list[ECell] :
        r_cells = []
        c = 1
        basic_count = len(self.cols_without_format)
        for col in row:
            if c in self.cols_without_format:
                r_cells.append(
                    ECell(
                        text=col, 
                        vertical_align=self.DefaultCellVerticalAlignment,
                        horizontal_align=self.DefaultCellHorizontalAlignment,
                        is_formula= False
                    )
                )
            else:
                origial_c = c-basic_count
                r_cells.append(
                    ECell(
                        text=self.get_cell_value(r,origial_c), 
                        vertical_align=self.DefaultCellVerticalAlignment,
                        horizontal_align=self.DefaultCellHorizontalAlignment,
                        is_formula= True
                    )
                )
            c+=1
        return r_cells

class S1(Template_WOS):
    def __init__(self, sheet_name, sheet_index, tab_name):
        super().__init__(sheet_name, sheet_index, tab_name)
        self._cols_without_format: set[int] = {1, 2, 3}

    def get_report(self) -> ExcelReport:
        report = ExcelReport()
        banner=ExcelColumnHeader(name=self.sheet_name, horizontal_align="center")
        serial_top = ExcelColumnHeader()
        serial_top.sub_headers = [ExcelColumnHeader(name=self.header_org_serial, horizontal_align= "left", width=15)]
        serial_name1_top = ExcelColumnHeader()
        serial_name1_top.sub_headers= [ExcelColumnHeader(name=self.header_org_name_1, horizontal_align= "left", width=15)]
        serial_name2_top = ExcelColumnHeader()
        serial_name2_top.sub_headers= [ExcelColumnHeader(name=self.header_org_name_2, horizontal_align= "left", width=15)]
        years = self.get_year_list()
        years_headers = []
        for y in years :
            year_header = ExcelColumnHeader(name=int(y), horizontal_align="center", width=20)
            years_headers.append(year_header)

        banner.sub_headers = years_headers
        report.headers = [serial_top, serial_name1_top, serial_name2_top, banner]
        return report 

    def get_cell_row(self, r:int, row : list[str]) -> list[ECell] :
        r_cells = []
        c = 1
        basic_count = len(self.cols_without_format)
        for col in row:
            if c in self.cols_without_format:
                r_cells.append(
                    ECell(
                        text=col, 
                        vertical_align=self.DefaultCellVerticalAlignment,
                        horizontal_align=self.DefaultCellHorizontalAlignment,
                        is_formula= False
                    )
                )
            elif ((c-basic_count-1) % 2) == 0:
                origial_c = c-basic_count
                str_format ="=TEXT({0},\"#,##0\")&CHAR(10)&\"(\"&TEXT({1},\"0.00%\")&\")\""
                str_format_empty = self.DefaultExcelFuncInteger
                if f"{r},{origial_c+1}" in self.null_val_loc:
                    r_cells.append(
                        ECell(
                            text=str_format_empty.format(self.get_cell_loc_str(r,origial_c)), 
                            vertical_align=self.DefaultCellVerticalAlignment,
                            horizontal_align=self.DefaultCellHorizontalAlignment,
                            is_formula= True
                        )
                    )
                else:
                    r_cells.append(
                        ECell(
                            text=str_format.format(self.get_cell_loc_str(r,origial_c), self.get_cell_loc_str(r,origial_c+1)), 
                            vertical_align=self.DefaultCellVerticalAlignment,
                            horizontal_align=self.DefaultCellHorizontalAlignment,
                            is_formula= True
                        )
                    )
            c+=1
            
        return r_cells

class S2(Template_WOS):
    def __init__(self, sheet_name, sheet_index, tab_name):
        super().__init__(sheet_name, sheet_index, tab_name)
        self._cols_without_format: set[int] = {1, 2, 3}
    
    def get_report(self) -> ExcelReport:
        report = ExcelReport()
        banner=ExcelColumnHeader(name=self.sheet_name, horizontal_align="center")
        serial_top = ExcelColumnHeader()
        serial_top.sub_headers = [ExcelColumnHeader(name=self.header_org_serial, horizontal_align= "left", width=15)]
        serial_name1_top = ExcelColumnHeader()
        serial_name1_top.sub_headers= [ExcelColumnHeader(name=self.header_org_name_1, horizontal_align= "left", width=15)]
        serial_name2_top = ExcelColumnHeader()
        serial_name2_top.sub_headers= [ExcelColumnHeader(name=self.header_org_name_2, horizontal_align= "left", width=15)]
        years = self.get_year_list()
        years_headers = []
        for y in years :
            year_header = ExcelColumnHeader(name=int(y), horizontal_align="center", width=20)
            years_headers.append(year_header)

        banner.sub_headers = years_headers
        report.headers = [serial_top, serial_name1_top, serial_name2_top, banner]
        return report   

    def get_cell_row(self, r:int, row : list[str]) -> list[ECell] :
        r_cells = []
        c = 1
        basic_count = len(self.cols_without_format)
        str_format ="=TEXT({0},\"#,##0\")&CHAR(10)&\"(\"&TEXT({1},\"#,##0\")&\";\"&TEXT({2},\"0%\")&\")\""
        for col in row:
            if c in self.cols_without_format:
                r_cells.append(
                    ECell(
                        text=col, 
                        vertical_align=self.DefaultCellVerticalAlignment,
                        horizontal_align=self.DefaultCellHorizontalAlignment,
                        is_formula= False
                    )
                )
            elif ((c-basic_count-1) % 3) == 0:
                origial_c = c-basic_count
                
                r_cells.append(
                    ECell(
                        text=str_format.format(self.get_cell_loc_str(r,origial_c), self.get_cell_loc_str(r,origial_c+1), self.get_cell_loc_str(r,origial_c+2)), 
                        vertical_align=self.DefaultCellVerticalAlignment,
                        horizontal_align=self.DefaultCellHorizontalAlignment,
                        is_formula= True
                    )
                )
            c+=1
            
        return r_cells

class S3(S2):
    def __init__(self, sheet_name, sheet_index, tab_name):
        super().__init__(sheet_name, sheet_index, tab_name)
        


class S4(Template_WOS):
    def __init__(self, sheet_name, sheet_index, tab_name):
        super().__init__(sheet_name, sheet_index, tab_name)
        self._cols_without_format: set[int] = {1, 2, 3}

    def get_report(self) -> ExcelReport:
        report = ExcelReport()
        banner=ExcelColumnHeader(name=self.sheet_name, horizontal_align="center")
        serial_top = ExcelColumnHeader()
        serial_top.sub_headers = [ExcelColumnHeader(name=self.header_org_serial, horizontal_align= "left", width=15)]
        serial_name1_top = ExcelColumnHeader()
        serial_name1_top.sub_headers= [ExcelColumnHeader(name=self.header_org_name_1, horizontal_align= "left", width=15)]
        serial_name2_top = ExcelColumnHeader()
        serial_name2_top.sub_headers= [ExcelColumnHeader(name=self.header_org_name_2, horizontal_align= "left", width=15)]
        years = self.get_year_list()
        years_headers = []
        for y in years :
            year_header = ExcelColumnHeader(name=int(y), horizontal_align="center", width=20)
            years_headers.append(year_header)

        banner.sub_headers = years_headers
        report.headers = [serial_top, serial_name1_top, serial_name2_top, banner]
        return report   
    

    def get_cell_value(self,r : int, c:int) -> str:
        cell_loc_str = self.get_cell_loc_str(r,c)
        check_str = f"{r},{c}"
        if check_str in self.null_val_loc:
            return ""

        return self.DefaultExcelFuncPercent.format(cell_loc_str)

class S5(S4):
    def __init__(self, sheet_name, sheet_index, tab_name):
        super().__init__(sheet_name, sheet_index, tab_name)

    def get_cell_value(self,r : int, c:int) -> str:
        cell_loc_str = self.get_cell_loc_str(r,c)
        check_str = f"{r},{c}"
        if check_str in self.null_val_loc:
            return ""

        return self.DefaultExcelFunc2DecimalPlace.format(cell_loc_str)

class S6(Template_WOS):
    
    def __init__(self, sheet_name, sheet_index, tab_name):
        super().__init__(sheet_name, sheet_index, tab_name)
        self.source : list[str] = ["SCIE", "SSCI", "AHCI"]
        self._cols_without_format: set[int] = {1, 2, 3, 4}
        # 要對照rawdata的column
        self._excel_func: dict[int, str] = {
            1:self.DefaultExcelFuncInteger,
            2:Template.DefaultExcelFuncPercent,
            3:self.DefaultExcelFuncInteger,
            4:Template.DefaultExcelFuncPercent,
            5:self.DefaultExcelFuncInteger,
            6:Template.DefaultExcelFuncPercent,
        }

    def get_report(self) -> ExcelReport:
        report = ExcelReport()

        headers = []
        serial_top = ExcelColumnHeader(name=self.header_org_serial, horizontal_align= "center", width=15)

        serial_name1_top=ExcelColumnHeader(name=self.header_org_name_1, horizontal_align= "center", width=15)

        serial_name2_top=ExcelColumnHeader(name=self.header_org_name_2, horizontal_align= "center", width=15)
        year = ExcelColumnHeader(width=12)

        headers = [serial_top, serial_name1_top, serial_name2_top, year]
        for s in self.source:
            source_header = ExcelColumnHeader(name=s, horizontal_align= "center")
            source_sub_pc_header = ExcelColumnHeader(name="論文數", horizontal_align= "center", width=12)
            source_sub_gr_header = ExcelColumnHeader(name="成長率", horizontal_align= "center", width=12)
            source_header.sub_headers = [source_sub_pc_header, source_sub_gr_header]
            headers.append(source_header)

        report.headers = headers
        return report

    def to_worksheet(self, wb, rows, basic_rows):
        self.rows = rows
        ## 建立rawdata_sheet
        self.rawdata_to_worksheet(wb, rows)

        report = self.get_report()
        report_rows : list[list[ECell]] = []
        y_list = self.get_year_list()
        y_total = len(self.get_year_list())
        for idx, rr in enumerate(self.rows):
            # 機構arr + year + 數值
            whole_row = basic_rows[int(idx/y_total)] + [int(y_list[int(idx%y_total)])] + rr
            rcells = self.get_cell_row(idx+1, whole_row)
            report_rows.append(rcells)

        report.rows = report_rows
        report.export(wb, self.sheet_tab_name)

    def get_cell_row(self, r:int, row : list[str]) -> list[ECell] :
        r_cells = []
        c = 1
        # 前三個是機構，需要垂直合併，垂直合併數字要看year
        # 第4格式年分，無公式
        # 後面6格是公式，看_excel_func填上
        basic_count = len(self.cols_without_format)
        y_total = self.get_year_count()
        for col in row:
            if c in self.cols_without_format and c != 4 :
                if (r % y_total) == 1 : 
                    r_cells.append(
                        ECell(
                            text=col, 
                            vertical_align=self.DefaultCellVerticalAlignment,
                            horizontal_align=self.DefaultCellHorizontalAlignment,
                            merge_row_range=y_total
                        )
                    )
                else:
                    r_cells.append(ECell(""))
            elif c == 4 :
                r_cells.append(
                    ECell(
                        text=col, 
                        vertical_align=self.DefaultCellVerticalAlignment,
                        horizontal_align=self.DefaultCellHorizontalAlignment
                    )
                )
            else:
                origial_c = c-basic_count
                r_cells.append(
                    ECell(
                        text=self.get_cell_value(r,origial_c), 
                        vertical_align=self.DefaultCellVerticalAlignment,
                        horizontal_align=self.DefaultCellHorizontalAlignment,
                        is_formula= True
                    )
                )
            c+=1
            
        return r_cells

class S7(Template_WOS):
    
    def __init__(self, sheet_name, sheet_index, tab_name, if_1_val, if_2_val):
        super().__init__(sheet_name, sheet_index, tab_name)
        self.source : list[str] = ["SCIE", "SSCI", "AHCI"]
        self._cols_without_format: set[int] = {1, 2, 3, 4}
        self.if_1_val = if_1_val
        self.if_2_val = if_2_val
        self.sheet_name = self.sheet_name.format(if_1_val,if_2_val)

    def get_report(self) -> ExcelReport:
        report = ExcelReport()

        headers = []
        serial_top = ExcelColumnHeader(name=self.header_org_serial,  width=15)
        serial_name1_top=ExcelColumnHeader(name=self.header_org_name_1, width=15)
        serial_name2_top=ExcelColumnHeader(name=self.header_org_name_2, width=15)
        desc_header = ExcelColumnHeader(width=20)
     
        years = self.get_year_list()
        years_headers = []
        for y in years :
            year_header = ExcelColumnHeader(name=int(y), width=20)
            years_headers.append(year_header)

        headers = [serial_top, serial_name1_top, serial_name2_top, desc_header] + years_headers

        report.headers = headers
        return report

    def to_worksheet(self, wb, rows, basic_rows):
        self.rows = rows
        ## 建立rawdata_sheet
        self.rawdata_to_worksheet(wb, rows)

        report = self.get_report()
        report_rows : list[list[ECell]] = []

        for idx, rr in enumerate(self.rows):
            # 機構arr + year + 數值
            whole_row = basic_rows[int(idx/3)] + [""] + rr
            rcells = self.get_cell_row(idx+1, whole_row)
            report_rows.append(rcells)

        report.rows = report_rows
        report.export(wb, self.sheet_tab_name)

    def get_cell_row(self, r:int, row : list[str]) -> list[ECell] :
        r_cells = []
        c = 1
        # 前三個是機構，需要垂直合併，垂直合併數字要看year
        # 第4格式有
        if_1_col_name = f"IF值{self.if_1_val}%論文數"
        if_2_col_name = f"IF值{self.if_2_val}%論文數"
        prcent_col_format ="=TEXT({0},\"#,##0\")&\"(\"&TEXT({1},\"0.0%\")&\")\""
        basic_count = len(self.cols_without_format)
        merge_row = 3
        for col in row:
            if c in self.cols_without_format and c != 4 :
                if (r % merge_row) == 1 : 
                    r_cells.append(
                        ECell(
                            text=col, 
                            vertical_align=self.DefaultCellVerticalAlignment,
                            horizontal_align=self.DefaultCellHorizontalAlignment,
                            merge_row_range=merge_row
                        )
                    )
                else:
                    r_cells.append(ECell(""))
            elif c == 4 :
                if r % merge_row == 1:
                    r_cells.append(
                        ECell(
                            text=row[1], 
                            vertical_align=self.DefaultCellVerticalAlignment,
                            horizontal_align=self.DefaultCellHorizontalAlignment
                        )
                    )
                elif r % merge_row == 2:
                    r_cells.append(
                        ECell(
                            text=if_1_col_name,
                            vertical_align=self.DefaultCellVerticalAlignment,
                            horizontal_align=self.DefaultCellHorizontalAlignment
                        )
                    )
                else:
                    r_cells.append(
                        ECell(
                            text=if_2_col_name, 
                            vertical_align=self.DefaultCellVerticalAlignment,
                            horizontal_align=self.DefaultCellHorizontalAlignment
                        )
                    )
            else:
                origial_c = c-basic_count
                
                if r % merge_row == 1:
                    r_cells.append(
                        ECell(
                            text=self.DefaultExcelFuncInteger.format(self.get_cell_loc_str(r,origial_c)), 
                            vertical_align=self.DefaultCellVerticalAlignment,
                            horizontal_align=self.DefaultCellHorizontalAlignment
                        )
                    )
                else:
                    if (origial_c % 2) == 1:
                        r_cells.append(
                            ECell(
                                text=prcent_col_format.format(self.get_cell_loc_str(r,origial_c),self.get_cell_loc_str(r,origial_c+1)),
                                vertical_align=self.DefaultCellVerticalAlignment,
                                horizontal_align=self.DefaultCellHorizontalAlignment
                            )
                        )
                    
            c+=1
            
        return r_cells   

class S9(S4):
    def __init__(self, sheet_name, sheet_index, tab_name):
        super().__init__(sheet_name, sheet_index, tab_name)

    def get_report(self) -> ExcelReport:
        report = ExcelReport()
        banner=ExcelColumnHeader(name=self.sheet_name, horizontal_align="center")
        serial_top = ExcelColumnHeader()
        serial_top.sub_headers = [ExcelColumnHeader(name=self.header_org_serial, horizontal_align= "left", width=15)]
        serial_name1_top = ExcelColumnHeader()
        serial_name1_top.sub_headers= [ExcelColumnHeader(name=self.header_org_name_1, horizontal_align= "left", width=15)]
        serial_name2_top = ExcelColumnHeader()
        serial_name2_top.sub_headers= [ExcelColumnHeader(name=self.header_org_name_2, horizontal_align= "left", width=15)]
        years = self.get_year_list(is_range=True)
        years_headers = []
        for y in years :
            year_header = ExcelColumnHeader(name=y, horizontal_align="center", width=20)
            years_headers.append(year_header)

        banner.sub_headers = years_headers
        report.headers = [serial_top, serial_name1_top, serial_name2_top, banner]
        return report   

