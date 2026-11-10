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
 *  - it does not reveal a test anybody could type into, and so does not have to
 *    make anything read-only. It reveals Composite, Constant and String
 *    Composite only - the three types in NO_SKIP_REQUIRED_TYPES, which are the
 *    types nobody enters, which is why they have no Skip checkbox either. Their
 *    controls are already readonly before this module touches them.
 *
 *    An earlier version revealed every hidden row and tried to neuter what it
 *    exposed with `prop('readonly', true)`. That is meaningless on a <select>
 *    or a radio, and never reached an upload's anchor at all, so a revealed
 *    boolean or multiple-choice test stayed fully editable - the one thing this
 *    feature promises cannot happen. Not revealing them removes the promise's
 *    only hard part.
 *
 *    A hidden test of an enterable type should not exist: the admin has always
 *    offered the Hidden checkbox for those three types alone, and TestForm.clean
 *    now clears the flag when a type change strands it. `qatrack.W016` reports
 *    any that predate that. Until a site is clean, such a row simply stays
 *    hidden, which is what it did before this feature existed.
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
 * Only rows this module hid are put back: it marks each one as it reveals it,
 * and a row that arrives without `hidden` is never given one.
 *
 * The comment row and the Skip checkbox needed handling while every hidden test
 * could be revealed. They do not now: a Composite, Constant or String Composite
 * has no Skip checkbox at all (that is what NO_SKIP_REQUIRED_TYPES means), and
 * its comment box is as readonly as the rest of it.
 */
define(['jquery'], function ($) {

    "use strict";

    var SHOW_CLASS = 'show-hidden-tests';
    var REVEALED_CLASS = 'qa-hidden-revealed';
    var ROW_MARKER = 'qahiddenRevealed';

    /* The three types nobody enters. qavalue_form.html puts the test's type on
     * its row as `qa-<type>`, so the page already says which is which. */
    var REVEALABLE = ['qa-composite', 'qa-constant', 'qa-scomposite'];

    function revealable_selector(state) {
        return REVEALABLE.map(function (cls) {
            return 'tr.' + state + '.' + cls;
        }).join(', ');
    }

    /* The rows this module is responsible for, in either state: still hidden, or
     * revealed by us. It has to match both, because revealing takes the class
     * that identified them away. A hidden row of any other type is deliberately
     * absent - see the header. */
    function hidden_rows($table) {
        return $table.children('tbody').children(
            revealable_selector('hidden') + ', ' + revealable_selector(REVEALED_CLASS)
        );
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
        return $('#qa-images').children('.qa-hidden-image, .' + REVEALED_CLASS);
    }

    function managed($table) {
        return $table.children('tbody').children('tr.hidden, tr.' + REVEALED_CLASS)
            .add(image_boxes());
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
            } else {
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
