## PRISAnalyzer.PresidentReportESI.Class.Analysis.Templates.ReportExporter

from dataclasses import dataclass, field
from openpyxl import Workbook
import os
# PRIS
from components.template import Template
from export.excel_report import *
from exceptions import PRISError

## 輸出成excel
## 統整所有sheet
@dataclass
class ReportExporter:
    #兩個list的位置是有對應的
    templates : list[Template] = field(default_factory=list)
    templates_rows : list[list[list[str]]] = field(default_factory=list)
    basic_rows : list[list[list[str]]] = field(default_factory=list) # 存放機構名稱等資訊

    def add_item(self, template: Template, template_row: list[list[str]], basic_row : list[list[str]] = None):
        self.templates.append(template)
        self.templates_rows.append(template_row)
        self.basic_rows.append(basic_row)

    # 匯出Excel檔案 - 對外入口
    def export(self, path : str):
        wb = Workbook()
        # openpyxl 預設會自動建立一個 "Sheet" 工作表,先移除
        if "Sheet" in wb.sheetnames:
            del wb["Sheet"]

        # 目錄Sheet
        self.create_table_of_contents(wb, self.templates)

        # 各類型的分析報表
        for r in range(len(self.templates)):
            self.templates[r].to_worksheet(wb=wb, rows= self.templates_rows[r])

        # 隱藏計算無排版的報表
        self.hide_all_rawdata_tabs(wb)

        #wb.save(path)
        self.save_file(wb, path)

    def save_file(self,wb:Workbook, output_path :str):
        if wb is None:
            raise PRISError("Save Workbook is empty!")
         
        if os.path.exists(output_path):
            print(f"檔案已存在,將被覆蓋:{output_path}")

        try:
            wb.save(output_path)
        except:
            raise PRISError("檔案可能正被其他程式開啟,請先關閉後再試")

    def create_table_of_contents(self, wb: Workbook, templates: list[Template]):
        excel_report = ExcelReport()

        header1 = ExcelColumnHeader(name= "表單名", width=15)
        header2 = ExcelColumnHeader(name= "表單內容", width=150)

        headers = [header1, header2]
        excel_report.headers = headers
        
        rows : list[list[ECell]] = []
        for temp in templates:
            row = [
                ECell(text=temp.sheet_tab_name),
                ECell(
                    text=temp.sheet_name, 
                    horizontal_align="left", 
                    hyperlink=f"#'{temp.sheet_tab_name}'!A1",
                )
            ]
            rows.append(row)

        excel_report.rows = rows
        excel_report.export(wb, "目錄")

    def hide_all_rawdata_tabs(self,  wb: Workbook):
        rawdata_sheet_suffix = Template.get_rawdata_sheet_suffix()
        for sheet in wb.worksheets:
            if sheet.title.endswith(rawdata_sheet_suffix):
                sheet.sheet_state = "hidden"

    def export_wos(self,path : str):
        wb = Workbook()
        # openpyxl 預設會自動建立一個 "Sheet" 工作表,先移除
        if "Sheet" in wb.sheetnames:
            del wb["Sheet"]

        # 各類型的分析報表
        for r in range(len(self.templates)):
            self.templates[r].to_worksheet(wb=wb, rows= self.templates_rows[r], basic_rows =self.basic_rows[r])

        # 隱藏計算無排版的報表
        self.hide_all_rawdata_tabs(wb)

        #wb.save(path)
        self.save_file(wb, path)            