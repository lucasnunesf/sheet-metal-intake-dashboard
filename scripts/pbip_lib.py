"""
pbip_lib: build a Power BI Project (.pbip) from a Python spec.

- Semantic model in TMDL: tables loaded from one Excel file through a DataFolder parameter,
  calculated columns, DAX measures, relationships (active / inactive).
- Report in PBIR: pages and visuals as JSON, plus a custom theme.

GUIDs are deterministic, so rebuilding does not create noisy git diffs.
"""
import json
import shutil
import uuid
from pathlib import Path

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"
S_VISUAL = f"{SCHEMA}/item/report/definition/visualContainer/2.4.0/schema.json"
S_PAGE = f"{SCHEMA}/item/report/definition/page/2.0.0/schema.json"
T = "\t"
_NS = uuid.UUID("6b1f3c1e-4c2a-4f7e-9a51-0c3d2e7f8a90")


# ------------------------------------------------------------------ helpers
def guid(key):
    return str(uuid.uuid5(_NS, key))


def vid(key):
    return uuid.uuid5(_NS, "visual:" + key).hex[:20]


def write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not isinstance(content, str):
        content = json.dumps(content, indent=2, ensure_ascii=False)
    path.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")


def tmdl_name(n):
    return n if n.replace("_", "").isalnum() else "'" + n.replace("'", "''") + "'"


# ------------------------------------------------------------------ model spec
class Model:
    """
    tables:   {name: [(column, m_type, tmdl_type, summarize_by, format_or_None), ...]}
    calc:     {table: [(column, tmdl_type, format, sort_by_or_None, [dax lines]), ...]}
    measures: {table: [(name, folder, format, [dax lines]), ...]}
    rels:     [(from_table, from_col, to_table, to_col, active), ...]
    sort_by:  {(table, column): sort_column}
    date_table: name of the table marked as date table (key column 'date')
    """

    def __init__(self, workbook, tables, measures, rels, calc=None, sort_by=None,
                 date_table="dCalendar", data_folder="C:\\data\\"):
        self.workbook, self.tables, self.measures, self.rels = workbook, tables, measures, rels
        self.calc, self.sort_by = calc or {}, sort_by or {}
        self.date_table, self.data_folder = date_table, data_folder

    def m_query(self, table):
        types = ", ".join(f'{{"{c}", {mt}}}' for c, mt, *_ in self.tables[table])
        return [
            "let",
            f'    Source = Excel.Workbook(File.Contents(DataFolder & "{self.workbook}"), null, true),',
            f'    Sheet = Source{{[Item="{table}",Kind="Sheet"]}}[Data],',
            "    Promoted = Table.PromoteHeaders(Sheet, [PromoteAllScalars=true]),",
            f"    Typed = Table.TransformColumnTypes(Promoted, {{{types}}})",
            "in",
            "    Typed",
        ]

    def table_tmdl(self, table):
        L = [f"table {table}", f"{T}lineageTag: {guid('table:' + table)}"]
        if table == self.date_table:
            L.append(f"{T}dataCategory: Time")
        L.append("")
        for name, folder, fmt, dax in self.measures.get(table, []):
            if len(dax) == 1:
                L.append(f"{T}measure {tmdl_name(name)} = {dax[0]}")
            else:
                L.append(f"{T}measure {tmdl_name(name)} =")
                L += [f"{T*3}{x}" for x in dax]
            L += [f"{T*2}formatString: {fmt}", f"{T*2}displayFolder: {folder}",
                  f"{T*2}lineageTag: {guid('measure:' + name)}", ""]
        for col, _mt, dt, summ, fmt in self.tables[table]:
            L.append(f"{T}column {tmdl_name(col)}")
            L.append(f"{T*2}dataType: {dt}")
            if fmt:
                L.append(f"{T*2}formatString: {fmt}")
            if table == self.date_table and col == "date":
                L.append(f"{T*2}isKey")
            L.append(f"{T*2}lineageTag: {guid(f'col:{table}.{col}')}")
            L.append(f"{T*2}summarizeBy: {summ}")
            L.append(f"{T*2}sourceColumn: {col}")
            if (table, col) in self.sort_by:
                L.append(f"{T*2}sortByColumn: {self.sort_by[(table, col)]}")
            L += ["", f"{T*2}annotation SummarizationSetBy = Automatic", ""]
        for col, dt, fmt, sort_col, dax in self.calc.get(table, []):
            L.append(f"{T}column {tmdl_name(col)} =")
            L += [f"{T*3}{x}" for x in dax]
            L.append(f"{T*2}dataType: {dt}")
            if fmt:
                L.append(f"{T*2}formatString: {fmt}")
            L.append(f"{T*2}lineageTag: {guid(f'col:{table}.{col}')}")
            L.append(f"{T*2}summarizeBy: none")
            if sort_col:
                L.append(f"{T*2}sortByColumn: {sort_col}")
            L += ["", f"{T*2}annotation SummarizationSetBy = Automatic", ""]
        L += [f"{T}partition {table} = m", f"{T*2}mode: import", f"{T*2}source ="]
        L += [f"{T*4}{x}" for x in self.m_query(table)]
        L += ["", f"{T}annotation PBI_ResultType = Table", ""]
        return "\n".join(L)

    def build(self, sm):
        write(sm / "definition.pbism", {
            "$schema": f"{SCHEMA}/item/semanticModel/definitionProperties/1.0.0/schema.json",
            "version": "4.2", "settings": {}})
        write(sm / "definition" / "database.tmdl", "database\n\tcompatibilityLevel: 1600\n")
        order = ["DataFolder"] + list(self.tables)
        write(sm / "definition" / "model.tmdl", "\n".join([
            "model Model", f"{T}culture: en-US",
            f"{T}defaultPowerBIDataSourceVersion: powerBI_V3",
            f"{T}sourceQueryCulture: en-US", f"{T}dataAccessOptions",
            f"{T*2}legacyRedirects", f"{T*2}returnErrorValuesAsNull", "",
            f"annotation PBI_QueryOrder = {json.dumps(order)}", "",
            "annotation __PBI_TimeIntelligenceEnabled = 0", "",
        ] + [f"ref table {t}" for t in self.tables]))
        write(sm / "definition" / "expressions.tmdl", "\n".join([
            f'expression DataFolder = "{self.data_folder}" meta [IsParameterQuery=true, '
            'Type="Text", IsParameterQueryRequired=true]',
            f"{T}lineageTag: {guid('expr:DataFolder')}", "",
            f"{T}annotation PBI_ResultType = Text", ""]))
        for t in self.tables:
            write(sm / "definition" / "tables" / f"{t}.tmdl", self.table_tmdl(t))
        rel = []
        for ft, fc, tt, tc, active in self.rels:
            rel.append(f"relationship {guid(f'rel:{ft}.{fc}-{tt}.{tc}')}")
            if not active:
                rel.append(f"{T}isActive: false")
            if tt == self.date_table:
                rel.append(f"{T}joinOnDateBehavior: datePartOnly")
            rel += [f"{T}fromColumn: {ft}.{fc}", f"{T}toColumn: {tt}.{tc}", ""]
        write(sm / "definition" / "relationships.tmdl", "\n".join(rel))


# ------------------------------------------------------------------ report helpers
def lit(v):
    if isinstance(v, bool):
        return {"expr": {"Literal": {"Value": "true" if v else "false"}}}
    if isinstance(v, (int, float)):
        return {"expr": {"Literal": {"Value": f"{v}D"}}}
    return {"expr": {"Literal": {"Value": "'" + str(v).replace("'", "''") + "'"}}}


def color(hex_):
    return {"solid": {"color": lit(hex_)}}


def col(entity, prop):
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def meas(entity, prop):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def proj(field, active=False):
    kind = "Measure" if "Measure" in field else "Column"
    ent, prop = field[kind]["Expression"]["SourceRef"]["Entity"], field[kind]["Property"]
    p = {"field": field, "queryRef": f"{ent}.{prop}", "nativeQueryRef": prop}
    if active:
        p["active"] = True
    return p


class Style:
    def __init__(self, dark, accent, text="#1F2A36", bg="#F3F4F6", line="#DDE2E8",
                 subtitle="#BFD4EA", palette=None):
        self.dark, self.accent, self.text, self.bg, self.line = dark, accent, text, bg, line
        self.subtitle = subtitle
        self.palette = palette or [accent, dark, "#2A9D8F", "#C8553D", "#8D99AE", "#F4B183"]

    def container(self, title=None):
        o = {"title": [{"properties": {"show": lit(False)}}]}
        if title:
            o["title"] = [{"properties": {"show": lit(True), "text": lit(title),
                                          "fontColor": color(self.text), "fontSize": lit(12),
                                          "bold": lit(True)}}]
        o["background"] = [{"properties": {"show": lit(True), "color": color("#FFFFFF"),
                                           "transparency": lit(0)}}]
        o["border"] = [{"properties": {"show": lit(True), "color": color(self.line), "radius": lit(8)}}]
        o["dropShadow"] = [{"properties": {"show": lit(True), "preset": lit("BottomRight"),
                                           "transparency": lit(85)}}]
        return o

    def theme(self, name):
        return {
            "name": name, "dataColors": self.palette, "background": "#FFFFFF",
            "foreground": self.text, "tableAccent": self.accent,
            "textClasses": {
                "label": {"fontFace": "Segoe UI", "fontSize": 10, "color": "#3A4452"},
                "title": {"fontFace": "Segoe UI Semibold", "fontSize": 12, "color": self.text},
                "callout": {"fontFace": "Segoe UI Semibold", "fontSize": 26, "color": self.text},
            },
            "visualStyles": {"page": {"*": {"background": [
                {"color": {"solid": {"color": self.bg}}, "transparency": 0}]}}},
        }


class Page:
    def __init__(self, name, display, style):
        self.name, self.display, self.s, self.visuals = name, display, style, []

    def add(self, key, x, y, w, h, visual, filters=None):
        v = {"$schema": S_VISUAL, "name": vid(self.name + key),
             "position": {"x": x, "y": y, "z": len(self.visuals) * 1000, "height": h,
                          "width": w, "tabOrder": len(self.visuals) * 1000},
             "visual": visual}
        if filters:
            v["filterConfig"] = {"filters": filters}
        self.visuals.append(v)

    # ---- visual factories
    def textbox(self, paragraphs, fill=None):
        pars = [{"textRuns": [{"value": t, "textStyle": st} for t, st in runs]} for runs in paragraphs]
        vco = {"title": [{"properties": {"show": lit(False)}}],
               "background": [{"properties": {"show": lit(bool(fill))} | (
                   {"color": color(fill), "transparency": lit(0)} if fill else {})}]}
        return {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": pars}}]},
                "visualContainerObjects": vco, "drillFilterOtherVisuals": True}

    def card(self, measure):
        return {"visualType": "card",
                "query": {"queryState": {"Values": {"projections": [proj(measure)]}}},
                "objects": {"labels": [{"properties": {"color": color(self.s.text), "fontSize": lit(26)}}],
                            "categoryLabels": [{"properties": {"show": lit(True), "color": color("#5B6573"),
                                                               "fontSize": lit(10)}}]},
                "visualContainerObjects": self.s.container(), "drillFilterOtherVisuals": True}

    def slicer(self, field, title):
        return {"visualType": "slicer",
                "query": {"queryState": {"Values": {"projections": [proj(field, active=True)]}}},
                "objects": {"data": [{"properties": {"mode": lit("Dropdown")}}],
                            "header": [{"properties": {"show": lit(True), "text": lit(title),
                                                       "fontColor": color(self.s.text)}}]},
                "visualContainerObjects": self.s.container(), "drillFilterOtherVisuals": True}

    def chart(self, vtype, category, y, title, y2=None, series=None, sort=None, sort_dir="Descending",
              fill=None, series_colors=None, labels=True):
        ys = y if isinstance(y, list) else [y]
        qs = {"Category": {"projections": [proj(category, active=True)]},
              "Y": {"projections": [proj(v) for v in ys]}}
        if y2 is not None:
            qs["Y2"] = {"projections": [proj(v) for v in (y2 if isinstance(y2, list) else [y2])]}
        if series is not None:
            qs["Series"] = {"projections": [proj(series)]}
        q = {"queryState": qs}
        if sort is not None:
            q["sortDefinition"] = {"sort": [{"field": sort, "direction": sort_dir}], "isDefaultSort": True}
        obj = {}
        if labels:
            obj["labels"] = [{"properties": {"show": lit(True), "color": color(self.s.text)}}]
        if fill:
            obj["dataPoint"] = [{"properties": {"fill": color(fill)}}]
        if series_colors:
            obj["dataPoint"] = [{"properties": {"fill": color(c)}, "selector": {"metadata": proj(m)["queryRef"]}}
                                for m, c in series_colors]
        if len(ys) > 1 or y2 is not None or series is not None:
            obj["legend"] = [{"properties": {"show": lit(True), "position": lit("Top")}}]
        obj["valueAxis"] = [{"properties": {"show": lit(False)}}] if vtype.endswith("BarChart") else \
            [{"properties": {"gridlineShow": lit(False)}}]
        return {"visualType": vtype, "query": q, "objects": obj,
                "visualContainerObjects": self.s.container(title), "drillFilterOtherVisuals": True}

    def table(self, fields, title, sort=None, sort_dir="Descending"):
        q = {"queryState": {"Values": {"projections": [proj(f) for f in fields]}}}
        if sort is not None:
            q["sortDefinition"] = {"sort": [{"field": sort, "direction": sort_dir}], "isDefaultSort": True}
        return {"visualType": "tableEx", "query": q,
                "objects": {"columnHeaders": [{"properties": {"backColor": color(self.s.dark),
                                                              "fontColor": color("#FFFFFF")}}],
                            "grid": [{"properties": {"gridHorizontalColor": color(self.s.line)}}]},
                "visualContainerObjects": self.s.container(title), "drillFilterOtherVisuals": True}

    def header(self, title, question, footer):
        self.add("title", 0, 0, 1280, 64, self.textbox([
            [(title, {"fontWeight": "bold", "fontSize": "20pt", "color": "#FFFFFF"})],
            [(question, {"fontSize": "11pt", "color": self.s.subtitle})]], fill=self.s.dark))
        self.add("footer", 860, 696, 412, 22, self.textbox([
            [(footer, {"fontSize": "8pt", "color": "#7A8494"})]]))


def categorical_filter(entity, prop, values, name):
    values = values if isinstance(values, list) else [values]
    return {"name": vid("filter:" + name), "field": col(entity, prop), "type": "Categorical",
            "filter": {"Version": 2, "From": [{"Name": "f", "Entity": entity, "Type": 0}],
                       "Where": [{"Condition": {"In": {
                           "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "f"}},
                                                       "Property": prop}}],
                           "Values": [[{"Literal": {"Value": f"'{v}'"}}] for v in values]}}}]},
            "howCreated": "User"}


# Standard layout on a 1280 x 720 page
CARD_X = [16 + i * 222 for i in range(4)]       # 4 cards, 210 wide
CARD_Y, CARD_W, CARD_H = 80, 210, 92
SLICER_1 = (904, 80, 176, 92)
SLICER_2 = (1092, 80, 172, 92)


# ------------------------------------------------------------------ build all
def build_project(out_dir, name, model: Model, pages, style: Style, theme_name):
    out_dir = Path(out_dir)
    sm, rp = out_dir / f"{name}.SemanticModel", out_dir / f"{name}.Report"
    for p in (sm, rp):
        if p.exists():
            shutil.rmtree(p)
    model.build(sm)
    write(rp / "definition.pbir", {
        "$schema": f"{SCHEMA}/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{name}.SemanticModel"}}})
    d = rp / "definition"
    write(d / "version.json", {"$schema": f"{SCHEMA}/item/report/definition/versionMetadata/1.0.0/schema.json",
                               "version": "2.0.0"})
    theme_file = f"{name}Theme.json"
    write(d / "report.json", {
        "$schema": f"{SCHEMA}/item/report/definition/report/3.0.0/schema.json",
        "themeCollection": {"customTheme": {
            "name": theme_file, "reportVersionAtImport": {"visual": "2.4.0", "report": "3.0.0", "page": "2.0.0"},
            "type": "RegisteredResources"}},
        "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources",
                              "items": [{"name": theme_file, "path": theme_file, "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True,
                     "allowChangeFilterTypes": True, "useEnhancedTooltips": True}})
    write(rp / "StaticResources" / "RegisteredResources" / theme_file, style.theme(theme_name))
    write(d / "pages" / "pages.json", {
        "$schema": f"{SCHEMA}/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p.name for p in pages], "activePageName": pages[0].name})
    for p in pages:
        write(d / "pages" / p.name / "page.json", {
            "$schema": S_PAGE, "name": p.name, "displayName": p.display, "displayOption": "FitToPage",
            "height": 720, "width": 1280,
            "objects": {"background": [{"properties": {"color": color(style.bg), "transparency": lit(0)}}]}})
        for v in p.visuals:
            write(d / "pages" / p.name / "visuals" / v["name"] / "visual.json", v)
    write(out_dir / f"{name}.pbip", {
        "$schema": f"{SCHEMA}/pbip/pbipProperties/1.0.0/schema.json", "version": "1.0",
        "artifacts": [{"report": {"path": f"{name}.Report"}}], "settings": {"enableAutoRecovery": True}})
    write(out_dir / ".gitignore", "**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")
    n = sum(len(p.visuals) for p in pages)
    nm = sum(len(v) for v in model.measures.values())
    print(f"Built {out_dir / (name + '.pbip')}: {len(model.tables)} tables, {nm} measures, "
          f"{len(pages)} pages, {n} visuals")
