import time


class ReportTransform(object):

    # *_id maps a source section id to a target section id
    # *_map maps fields inside the section from source to target id
    # and treats the third value as a default value that is going to
    # be ignored

    blue_id = (None, None)
    blue_map = []
    cell_id = (None, None)
    cell_map = []
    position_id = (None, None)
    position_map = []
    toplevel_map = []
    wifi_id = (None, None)
    wifi_map = []

    def conditional_set(self, item, target, value, missing):
        if value is not None and value != missing:
            item[target] = value

    def _parse_blues(self, item, report):
        blues = []
        for blue_item in item.get(self.blue_id[0], ()):
            blue = {}
            for source, target, missing in self.blue_map:
                self.conditional_set(blue, target,
                                     blue_item[source], missing)
            if blue:
                blues.append(blue)
        if blues:
            report[self.blue_id[1]] = blues
        return blues

    def _parse_cells(self, item, report):
        cells = []
        item_radio = item['radioType']
        for cell_item in item.get(self.cell_id[0], ()):
            cell = {}
            for source, target, missing in self.cell_map:
                self.conditional_set(cell, target,
                                     cell_item[source], missing)
            if cell:
                if 'radioType' not in cell and item_radio:
                    cell['radioType'] = item_radio
                if cell.get('radioType') == 'umts':
                    cell['radioType'] = 'wcdma'
                cells.append(cell)
        if cells:
            report[self.cell_id[1]] = cells
        return cells

    def _parse_position(self, item, report):
        position = {}
        if self.position_id[0] is None:
            item_position = item
        else:
            item_position = item.get(self.position_id[0])
        if item_position:
            for source, target, missing in self.position_map:
                self.conditional_set(position, target,
                                     item_position[source], missing)
        report[self.position_id[1]] = position
        return position

    def _parse_toplevel(self, item, report):
        for source, target, missing in self.toplevel_map:
            self.conditional_set(report, target, item[source], missing)
        return report

    def _parse_wifis(self, item, report):
        wifis = []
        for wifi_item in item.get(self.wifi_id[0], ()):
            wifi = {}
            for source, target, missing in self.wifi_map:
                self.conditional_set(wifi, target,
                                     wifi_item[source], missing)
            if wifi:
                wifis.append(wifi)
        if wifis:
            report[self.wifi_id[1]] = wifis
        return wifis

    def _parse_timestamp(self, item, report):
        if not item['timestamp']:
            report['timestamp'] = time.time() * 1000.0
        else:
            report['timestamp'] = item['timestamp']

    def _parse_extra(self, item, report):  # pragma: no cover
        pass

    def transform(self, items):
        reports = []
        for item in items:
            report = {}
            self._parse_extra(item, report)
            self._parse_position(item, report)
            self._parse_toplevel(item, report)

            blues = self._parse_blues(item, report)
            cells = self._parse_cells(item, report)
            wifis = self._parse_wifis(item, report)

            if blues or cells or wifis:
                reports.append(report)

        return reports
