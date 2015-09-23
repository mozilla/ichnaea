(function($) {
    $(function() {
        var $table = $('#country-stats').dataTable({
            info: false,
            paging: true,
            searching: true,
            pageLength: 25,
            order: [[4, "desc"]]
        });
    });
}(jQuery));
