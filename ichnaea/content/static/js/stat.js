var XHover = Rickshaw.Class.create(Rickshaw.Graph.HoverDetail, {

    formatter: function(series, x, y, formattedX, formattedY, d) {
        return formattedX + ':&nbsp;' + formattedY;
    },

    render: function(args) {

        var graph = this.graph;
        var points = args.points;
        var point = points.filter(function(p) {
            return p.active;
        }).shift();

        if (point.value.y === null) return;

        var formattedXValue = point.formattedXValue;
        var formattedYValue = point.formattedYValue;

        this.element.innerHTML = '';
        this.element.style.left = graph.x(point.value.x) + 'px';

        var item = document.createElement('div');
        item.className = 'item';

        // invert the scale if this series displays using a scale
        var series = point.series;
        var actualY = series.scale ? series.scale.invert(point.value.y) : point.value.y;

        item.innerHTML = this.formatter(
            series, point.value.x, actualY, formattedXValue, formattedYValue, point);
        item.style.top = this.graph.y(point.value.y0 + point.value.y) + 'px';

        this.element.appendChild(item);

        var dot = document.createElement('div');

        dot.className = 'dot';
        dot.style.top = item.style.top;
        dot.style.borderColor = series.color;

        this.element.appendChild(dot);

        if (point.active) {
            item.className = 'item active';
            dot.className = 'dot active';
        }

        this.show();

        if (typeof this.onRender == 'function') {
            this.onRender(args);
        }
    }
});

function make_graph(url, graph_id) {
    var result = {};
    $.ajax({
        url: url,
        dataType: "json",
        async: false,
        success: function(json) {
            result = json;
        }
    });

    var entries = [];
    var item;
    for (var i = 0; i < result.histogram.length; i++) {
        item = result.histogram[i];
        entries.push({x: Date.parse(item.day), y: item.num});
    }

    var graph = new Rickshaw.Graph( {
        element: document.querySelector(graph_id + " .chart"),
        width: 720,
        height: 120,
        renderer: 'area',
        series: [ {
                data: entries,
                color: 'steelblue'
        } ]
    } );

    var format_date = function(n) {
        var d = new Date(0);
        d.setUTCMilliseconds(n);
        return d.toLocaleDateString();
    };

    var x_axis = new Rickshaw.Graph.Axis.X( {
        graph: graph,
        orientation: 'bottom',
        element: document.querySelector(graph_id + " .chart_x_axis"),
        pixelsPerTick: 100,
        tickFormat: format_date
    } );

    var y_axis = new Rickshaw.Graph.Axis.Y( {
        graph: graph,
        orientation: 'left',
        element: document.querySelector(graph_id + " .chart_y_axis"),
        pixelsPerTick: 72,
        tickFormat: Rickshaw.Fixtures.Number.formatKMBT
    } );

    var hoverDetail = new XHover( {
        graph: graph,
        xFormatter: format_date,
        yFormatter: function(y) {
            return y;
        }
    } );

    graph.render();
}

$(document).ready(function() {
    make_graph('/stats_location.json', '#location_chart');
    make_graph('/stats_unique_cell.json', '#unique_cell_chart');
    make_graph('/stats_unique_wifi.json', '#unique_wifi_chart');
});
