/*jslint browser: true */
/*global define */

/* Reveal the tests a test list marks hidden, without letting that change what
 * gets submitted.
 *
 * A hidden test (`Test.hidden`, "Don't display this test when performing QC")
 * is almost always an intermediate value that a composite depends on. Its row
 * is rendered in full - every input, its comment and procedure rows - and only
 * CSS-hidden, so showing it is a class on the table rather than anything to do
 * with the form, the view or the query.
 *
 * Two things this deliberately does NOT do:
 *
 *  - it does not call `TestInstance.show()`/`hide()`. Those set `visible`, and a
 *    test that is not visible has its value nulled on submit ("Filtered values
 *    will be nulled on submitt" in qa.js) - which for a hidden test would throw
 *    away the computed value the test exists to store.
 *  - it does not leave a revealed input editable. A composite or constant is
 *    already readonly; a hidden *simple* test is not, and is only unreachable
 *    because nobody can see it. Revealing it would quietly make it editable, so
 *    this marks what it reveals readonly and puts that back on hiding again.
 *    Only inputs it made readonly itself are restored, never one that was
 *    readonly to begin with.
 *
 * A test's row is not the only thing that decides what it submits. Its comment
 * lives in a sibling row (`#<slug>-comment-row`, which carries no `hidden`
 * class of its own), and a simple test also has a Skip checkbox in its own row.
 * Both were unreachable while the row was hidden, so both are covered here:
 * the comment box the same way as the value, and the Skip checkbox by CSS,
 * because `readonly` has no effect on a checkbox and `disabled` would drop it
 * from the POST - changing what is submitted, which is the one thing this is
 * not allowed to do.
 */
define(['jquery'], function ($) {

    "use strict";

    var SHOW_CLASS = 'show-hidden-tests';
    var MARKER = 'qahiddenReadonly';

    function hidden_rows($table) {
        return $table.children('tbody').children('tr.hidden');
    }

    /* Every control a revealed test can submit: its own inputs, and the comment
     * box in the sibling row that `tr.hidden` does not include. The two rows are
     * tied together by the form prefix class both carry, `row-<prefix>`, which
     * is also how the rest of the page finds one from the other. */
    function controls($table) {
        var $rows = hidden_rows($table);
        var $comments = $();
        $rows.each(function () {
            var prefix = $(this).data('prefix');
            if (prefix !== undefined && prefix !== null && prefix !== '') {
                $comments = $comments.add(
                    $table.children('tbody').children('tr.qa-comment.row-' + prefix)
                );
            }
        });
        return $rows.add($comments)
            .find('input.qa-input, textarea.qa-input, select.qa-input, textarea[name$="-comment"]');
    }

    function lock($table) {
        controls($table).each(function () {
            var $input = $(this);
            if ($input.prop('readonly') || $input.prop('disabled')) {
                return;
            }
            $input.prop('readonly', true).data(MARKER, true);
        });
    }

    function unlock($table) {
        controls($table).each(function () {
            var $input = $(this);
            if ($input.data(MARKER)) {
                $input.prop('readonly', false).removeData(MARKER);
            }
        });
    }

    /* Call with the table and the checkbox that drives it. Returns a function
     * that applies the checkbox's current state, so a caller can re-apply it
     * after anything that re-renders rows. */
    return function show_hidden_tests(table, toggle) {
        var $table = $(table);
        var $toggle = $(toggle);

        if ($table.length === 0 || $toggle.length === 0) {
            return function () { return false; };
        }

        function apply() {
            var showing = $toggle.is(':checked');
            if (showing) {
                lock($table);
            } else {
                unlock($table);
            }
            $table.toggleClass(SHOW_CLASS, showing);
            $.Topic("hiddenTestsToggled").publish(showing);
            return showing;
        }

        // The page's checkbox is wrapped by iCheck (sidebar.js), and iCheck 1.0.2
        // reports a click as 'ifChanged' and never fires 'change', so listen for
        // both: 'change' for a plain checkbox, 'ifChanged' for the real page.
        $toggle.on('change ifChanged', apply);
        apply();
        return apply;
    };
});
