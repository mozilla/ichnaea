(function($) {
    $(function() {
        var $table = $('#region-stats').dataTable({
            info: false,
            paging: true,
            searching: true,
            pageLength: 25,
            order: [[5, "desc"]]
        });
    });
}(jQuery));
