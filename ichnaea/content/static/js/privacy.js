$(function() {
    "use strict";

    // Create text translation function using #strings element.
    var $strings = $('#strings');
    window.trans = function trans(stringId) {
        return $strings.data(stringId);
    };

    var panel_open_text = window.trans('tabpanel-open-text');
    var panel_close_text = window.trans('tabpanel-close-text');

    // Accordion widgets in the highlight box
    $('#main-content .accordion').each(function(accordionIndex) {
        $(this).attr({
          'role': 'tablist',
          'aria-multiselectable': 'true'
        }).find('[role="tab"]').each(function(tabIndex) {
            var expanded = false;
            var id = this.id || $(this).parent().attr('id')
                             || 'accordion-' + accordionIndex + '-tab-' + tabIndex;
            var $tab = $(this).attr({
              'tabindex': '-1',
              'aria-controls': id + '-tabpanel',
              'aria-expanded': 'false'
            });
            var $panel = $('#' + $(this).attr('aria-controls'));
            var $anchor = $('<a href="#" role="button">' + panel_open_text + '</a>');

            if (!$panel.length) {
              $panel = $tab.next('[role="tabpanel"]').attr('id', id + '-tabpanel');
            }

            $panel.attr({
              'tabindex': '-1',
              'aria-hidden': 'true'
            });

            $tab.on('click', function (event) {
                event.preventDefault();
                expanded = !expanded;
                $tab.attr('aria-expanded', expanded);
                $panel.attr('aria-hidden', !expanded);
                $anchor.text((expanded) ? panel_close_text : panel_open_text);
            });

            $anchor.on('click', function (event) {
                event.preventDefault();
            }).appendTo(($tab.find(':last-child').length) ? $tab.find(':last-child') : $tab);
        });
    });

});
