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
 * How a row is revealed: by taking Bootstrap's `hidden` class OFF it, not by
 * out-specifying `display: none !important` with a rule of our own. The first
 * version did the latter, and an author !important beats an inline style - so
 * `TestInstance.hide()`, which the category filter uses and which sets
 * `display: none` on the element, could no longer hide a revealed row. Deselect
 * every category with the reveal on and the page showed nothing but the hidden
 * rows, each one marked skipped. Removing the class instead leaves `show()` and
 * `hide()` working normally, and no rule anywhere needs !important.
 *
 * Only rows this module hid are put back, the same discipline as the readonly
 * marker: a row that arrives without `hidden` is never given one.
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
    var REVEALED_CLASS = 'qahidden-revealed';
    var MARKER = 'qahiddenReadonly';
    var ROW_MARKER = 'qahiddenRevealed';

    /* The rows this module is responsible for, in either state: still hidden, or
     * revealed by us. It has to match both, because revealing takes the class
     * that identified them away. */
    function hidden_rows($table) {
        return $table.children('tbody').children('tr.hidden, tr.' + REVEALED_CLASS);
    }

    /* Reveal and re-hide take a set rather than the table, because a hidden test
     * has something to hide outside it: its image box. */
    function reveal($els) {
        $els.filter('.hidden').each(function () {
            $(this).removeClass('hidden').addClass(REVEALED_CLASS).data(ROW_MARKER, true);
        });
    }

    function rehide($els) {
        $els.filter('.' + REVEALED_CLASS).each(function () {
            var $el = $(this);
            if ($el.data(ROW_MARKER)) {
                $el.removeClass(REVEALED_CLASS).addClass('hidden').removeData(ROW_MARKER);
            }
        });
    }

    /* `display_image` renders into #qa-images, a container OUTSIDE the table, so
     * hiding a test's row never hid its image - or the heading above it, which
     * names the test. Both are the thing `hidden` exists to suppress, so they
     * are revealed and re-hidden with the rows rather than separately. */
    function image_boxes() {
        return $('#qa-images').children('.qahidden-image, .' + REVEALED_CLASS);
    }

    function managed($table) {
        return $table.children('tbody').children('tr.hidden, tr.' + REVEALED_CLASS)
            .add(image_boxes());
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
                reveal(managed($table));
                lock($table);
            } else {
                unlock($table);
                rehide(managed($table));
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
