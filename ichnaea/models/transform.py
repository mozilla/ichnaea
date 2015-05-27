

class ReportTransform(object):

    # *_id maps a source section id to a target section id
    # *_map maps fields inside the section from source to target id
    # if the names are equal, a simple string can be specified instead
    # of a two-tuple

    time_id = None

    blue_id = (None, None)
    blue_map = []

    radio_id = (None, None)
    cell_id = (None, None)
    cell_map = []

    position_id = (None, None)
    position_map = []

    toplevel_map = []

    wifi_id = (None, None)
    wifi_map = []

    def conditional_set(self, item, target, value):
        if value is not None:
            item[target] = value

    def _parse_blues(self, item, report):
        blues = []
        for blue_item in item.get(self.blue_id[0], ()):
            blue = {}
            for spec in self.blue_map:
                if isinstance(spec, tuple):  # pragma: no cover
                    source, target = spec
                else:
                    source = spec
                    target = spec
                self.conditional_set(blue, target, blue_item.get(source))
            if blue:
                blues.append(blue)
        if blues:
            report[self.blue_id[1]] = blues
        return blues

    def _parse_cells(self, item, report):
        cells = []
        item_radio = item.get(self.radio_id[0])
        for cell_item in item.get(self.cell_id[0], ()):
            cell = {}
            for spec in self.cell_map:
                if isinstance(spec, tuple):
                    source, target = spec
                else:
                    source = spec
                    target = spec
                self.conditional_set(cell, target, cell_item.get(source))
            if cell:
                if not cell.get(self.radio_id[1]) and item_radio:
                    cell[self.radio_id[1]] = item_radio
                if cell.get(self.radio_id[1]) == 'umts':
                    cell[self.radio_id[1]] = 'wcdma'
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
            for spec in self.position_map:
                if isinstance(spec, tuple):
                    source, target = spec
                else:
                    source = spec
                    target = spec
                self.conditional_set(position, target,
                                     item_position.get(source))
        if position:
            report[self.position_id[1]] = position
        return position

    def _parse_toplevel(self, item, report):
        for spec in self.toplevel_map:
            if isinstance(spec, tuple):  # pragma: no cover
                source, target = spec
            else:
                source = spec
                target = spec
            self.conditional_set(report, target, item.get(source))
        return report

    def _parse_wifis(self, item, report):
        wifis = []
        for wifi_item in item.get(self.wifi_id[0], ()):
            wifi = {}
            for spec in self.wifi_map:
                if isinstance(spec, tuple):
                    source, target = spec
                else:
                    source = spec
                    target = spec
                self.conditional_set(wifi, target, wifi_item.get(source))
            if wifi:
                wifis.append(wifi)
        if wifis:
            report[self.wifi_id[1]] = wifis
        return wifis

    def transform_one(self, item):
        report = {}
        self._parse_position(item, report)
        self._parse_toplevel(item, report)

        timestamp = item.get(self.time_id)
        if timestamp:
            report['timestamp'] = timestamp

        blues = self._parse_blues(item, report)
        cells = self._parse_cells(item, report)
        wifis = self._parse_wifis(item, report)

        if blues or cells or wifis:
            return report
        return {}

    def transform_many(self, items):
        reports = []
        for item in items:
            report = self.transform_one(item)
            if report:
                reports.append(report)

        return reports
