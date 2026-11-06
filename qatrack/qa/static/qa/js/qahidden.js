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
 */
define(['jquery'], function ($) {

    "use strict";

    var SHOW_CLASS = 'show-hidden-tests';
    var MARKER = 'qahiddenReadonly';

    function hidden_rows($table) {
        return $table.children('tbody').children('tr.hidden');
    }

    function lock($table) {
        hidden_rows($table).find('input.qa-input, textarea.qa-input, select.qa-input')
            .each(function () {
                var $input = $(this);
                if ($input.prop('readonly') || $input.prop('disabled')) {
                    return;
                }
                $input.prop('readonly', true).data(MARKER, true);
            });
    }

    function unlock($table) {
        hidden_rows($table).find('[readonly]').each(function () {
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

        $toggle.on('change', apply);
        apply();
        return apply;
    };
});
