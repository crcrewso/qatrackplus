/*jslint browser: true */
/*global define */

/* #818: alternating row shading for the QC tables.
 *
 * This is the table half of the form striping in
 * qatrack_core/static/qatrack_core/css/base.css. It adds the `qa-row-even`
 * class, which qa/css/qa.css gives a background, to every second *test*.
 *
 * Why this is script, where the plain forms get away with a
 * `forloop.counter|divisibleby:2` in the template:
 *
 *  - a test is a block of rows, not a row. Its value row is followed by the
 *    comment, procedure, text-display and attachment rows that belong to it,
 *    and preceded by an error row when the form came back invalid. Shading row
 *    by row would cut a test in half, and the number of rows per test varies
 *    from two to five, so `:nth-child` cannot group them either.
 *  - the perform page hides whole tests at runtime. The category filter calls
 *    show()/hide() on a test's rows, so a parity baked into the markup is
 *    wrong the moment anyone filters: every test after a hidden one keeps the
 *    shade it was rendered with. Counting only the tests that are actually on
 *    screen, every time, is the only way the alternation survives.
 *
 * Call it again after anything that shows, hides or re-renders rows.
 */
define(['jquery'], function ($) {

    "use strict";

    var STRIPE_CLASS = 'qa-row-even';

    /* A row that starts something new, so the preceding test's block ends
     * here.
     *
     * `tr.qa-error` is in the list even though an error row belongs to a test:
     * it sits *before* that test's value row, so without it the walk from test
     * N runs straight through N+1's error rows and stops only at N+1's value
     * row. N+1's red error bar would then carry N's shade while N+1's own rows
     * did not - the row grouped with the wrong test, which is the one thing
     * this module exists to prevent. Nothing is lost by breaking here, because
     * a test's own error rows carry its form prefix and arrive through the
     * branch below.
     *
     * The sublist delimiters - `tr.sublist` opening one and `tr.end-sublist`
     * closing it - belong to no test and keep the table's own background. */
    var BLOCK_BREAK = 'tr.qa-valuerow, tr.sublist, tr.qa-error, tr.end-sublist';

    function rows_for_test($value_row) {
        /* The companion rows that follow it, plus any row carrying this test's
         * form prefix - the perform page's error rows sit *before* the value
         * row, so following rows alone would miss them. */
        var $rows = $value_row.add($value_row.nextUntil(BLOCK_BREAK));
        var prefix = $value_row.attr('data-prefix');
        if (prefix) {
            $rows = $rows.add($value_row.closest('tbody').children('tr.row-' + prefix));
        }
        return $rows;
    }

    return function stripe_qa_rows(table) {
        var $body = $(table).children('tbody');
        if ($body.length === 0) {
            return;
        }

        $body.children('tr').removeClass(STRIPE_CLASS);

        var visible_tests = 0;
        $body.children('tr.qa-valuerow').each(function () {
            var $value_row = $(this);
            /* The row's own computed display, not :hidden, which also answers
             * yes for a visible row inside a container that is still hidden
             * while the page is being set up. */
            if ($value_row.css('display') === 'none') {
                return;
            }
            visible_tests += 1;
            if (visible_tests % 2 === 0) {
                rows_for_test($value_row).addClass(STRIPE_CLASS);
            }
        });
    };
});
