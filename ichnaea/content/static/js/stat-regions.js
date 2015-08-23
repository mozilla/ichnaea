(function($) {
    $(function() {
        var $table = $('#country-stats').DataTable({
            info: false,
            paging: true,
            searching: true,
            pageLength: 25,
            order: [[5, "desc"]]
        });
    });
}(jQuery));
