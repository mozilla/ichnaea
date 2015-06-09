(function($) {
    $(function() {
        var $table = $('#country-stats').DataTable({
            info: false,
            paging: false,
            searching: false
        });
        var header = new $.fn.dataTable.FixedHeader($table);
        $(window).on('resize', function() {
            header.fnDisable();
            $('.FixedHeader_Cloned').remove();
            header = new $.fn.dataTable.FixedHeader($table);
        });
    });
}(jQuery));
