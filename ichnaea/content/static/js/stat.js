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
    var graphWidth = 720;
    var graphHeight = 120;
    var graphXScale = 170;
    var graphYScale = 50;

    // adjust graph sizes to match responsive CSS rules
    var screenWidth = screen.width;
    if (screenWidth >= 760 && screenWidth < 1000) {
        graphWidth = 520;
        graphXScale = 160;
    } else if (screenWidth < 760) {
        graphWidth = 220;
    }

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
    var item_day_array;
    var item_day;
    for (var i = 0; i < result.histogram.length; i++) {
        item = result.histogram[i];
        item_day_array = item.day.split('-');
        item_day = Date.UTC(
            parseInt(item_day_array[0], 10),
            parseInt(item_day_array[1], 10),
            parseInt(item_day_array[2], 10));
        entries.push({x: item_day, y: item.num});
    }

    var graph = new Rickshaw.Graph( {
        element: document.querySelector(graph_id + " .chart"),
        width: graphWidth,
        height: graphHeight,
        renderer: 'area',
        series: [ {
                data: entries,
                color: 'steelblue'
        } ]
    } );

    function pad(number) {
        if ( number < 10 ) {
            return '0' + number;
        }
        return number;
    }

    var format_date = function(n) {
        var d = new Date(0);
        d.setUTCMilliseconds(n);
        return d.getUTCFullYear() +
            '-' + pad(d.getUTCMonth() + 1) +
            '-' + pad(d.getUTCDate());
    };

    var x_axis = new Rickshaw.Graph.Axis.X( {
        graph: graph,
        orientation: 'bottom',
        element: document.querySelector(graph_id + " .chart_x_axis"),
        pixelsPerTick: graphXScale,
        tickFormat: format_date
    } );

    var y_axis = new Rickshaw.Graph.Axis.Y( {
        graph: graph,
        orientation: 'left',
        element: document.querySelector(graph_id + " .chart_y_axis"),
        pixelsPerTick: graphYScale,
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
