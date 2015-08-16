(function($) {
    $(function() {
        var $table = $('#country-stats').DataTable({
            info: false,
            paging: true,
            searching: true,
            pageLength: 25,
            order: [[5, "desc"]]
        });
        var header = new $.fn.dataTable.FixedHeader($table);
        $(window).on('resize', function() {
            header.fnDisable();
            $('.FixedHeader_Cloned').remove();
            header = new $.fn.dataTable.FixedHeader($table);
        });
    });
}(jQuery));
