odoo.define('crm_commissions.total_footer', function (require) {
    "use strict";

    var ListRenderer = require('web.ListRenderer');

    ListRenderer.include({
        _renderGroupRow: function (group, groupLevel) {
            var self = this;
            return this._super.apply(this, arguments).then(function ($groupRow) {
                // Find the total row and move it to the bottom
                var $totalRow = $groupRow.next('.o_group_total_row');
                if ($totalRow.length) {
                    $totalRow.detach();
                    $groupRow.closest('tbody').append($totalRow);
                }
                return $groupRow;
            });
        },
    });
});