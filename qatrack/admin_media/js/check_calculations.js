/*
 * Check Calculation Procedures admin page (see qatrack/qa/calculation_check.py).
 *
 * The page arrives with every procedure already scanned. Recalculating posts
 * the planned jobs to the server one at a time, so that no single request
 * runs for long, and adds each result to its test's row as it arrives.
 */
(function () {
    'use strict';

    var data = JSON.parse(document.getElementById('cc-data').textContent);
    var strings = data.strings;
    var button = document.getElementById('cc-recalculate');
    var progress = document.getElementById('cc-progress');
    var problemsOnly = document.getElementById('cc-problems-only');
    var summary = document.getElementById('cc-summary');
    var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    var entries = {};
    document.querySelectorAll('#cc-table tbody tr').forEach(function (row) {
        entries[row.dataset.testId] = {row: row, statuses: [row.dataset.scanStatus], ran: false};
    });

    function format(template, values) {
        return template.replace(/%\((\w+)\)s/g, function (match, key) {
            return values[key];
        });
    }

    // Mirrors calculation_check.worst()
    function worst(statuses) {
        for (var i = 0; i < data.severity.length; i++) {
            if (statuses.indexOf(data.severity[i]) >= 0) {
                return data.severity[i];
            }
        }
        return 'ok';
    }

    function statusOf(entry) {
        return entry.row.dataset.status || entry.row.dataset.scanStatus;
    }

    function setStatus(entry, status) {
        var badge = entry.row.querySelector('.cc-status');
        badge.className = 'cc-status cc-' + status;
        badge.textContent = data.statusDisplay[status];
        entry.row.dataset.status = status;
    }

    function element(tag, className, text) {
        var el = document.createElement(tag);
        if (className) {
            el.className = className;
        }
        if (text !== undefined) {
            el.textContent = text;
        }
        return el;
    }

    function addResult(entry, result) {
        var item = element('li', 'cc-recalc');
        item.dataset.status = result.severity;

        var text = result.status_display + ': ' + result.source;
        if (result.message) {
            text += ' – ' + result.message;
        }
        item.appendChild(element('span', null, text));

        // Values are shown when they differ, or when there was nothing saved to
        // compare with (sample files, default values); identical ones are noise.
        var values = [];
        if (result.status === 'changed' && result.saved) {
            values.push(strings.saved + ': ' + result.saved);
        }
        if (result.recalculated && (result.status === 'changed' || !result.saved)) {
            values.push(strings.recalculated + ': ' + result.recalculated);
        }
        values = values.concat(result.warnings || []);
        if (values.length) {
            item.appendChild(element('div', 'cc-values', values.join('\n')));
        }

        if (result.detail) {
            var details = element('details');
            details.appendChild(element('summary', null, strings.details));
            details.appendChild(element('pre', 'cc-traceback', result.detail));
            item.appendChild(details);
        }

        entry.row.querySelector('.cc-details').appendChild(item);
    }

    function addNote(entry, text) {
        entry.row.querySelector('.cc-details').appendChild(element('li', 'cc-recalc cc-quiet', text));
    }

    function update() {
        var counts = {};
        Object.keys(entries).forEach(function (id) {
            var entry = entries[id];
            var status = statusOf(entry);
            counts[status] = (counts[status] || 0) + 1;
            entry.row.classList.toggle('cc-hidden', problemsOnly.checked && status === 'ok');
        });
        summary.textContent = data.severity.filter(function (status) {
            return counts[status];
        }).map(function (status) {
            return counts[status] + ' ' + data.statusDisplay[status];
        }).join(' · ');
    }

    function failedJob(job, error) {
        return job.test_ids.map(function (testId) {
            return {
                test_id: testId,
                status: 'error',
                severity: 'error',
                status_display: data.statusDisplay.error,
                source: '',
                message: format(strings.serverError, {error: error.message}),
                warnings: [],
            };
        });
    }

    function runJob(job) {
        return fetch(data.runUrl, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
            body: JSON.stringify(job),
        }).then(function (response) {
            if (!response.ok) {
                throw new Error(response.status + ' ' + response.statusText);
            }
            return response.json();
        }).then(function (body) {
            return body.results;
        }).catch(function (error) {
            return failedJob(job, error);
        });
    }

    function recalculate() {
        button.disabled = true;

        // start again from the scan, in case this is a second run
        Object.keys(entries).forEach(function (id) {
            var entry = entries[id];
            entry.statuses = [entry.row.dataset.scanStatus];
            entry.ran = false;
            delete entry.row.dataset.status;
            entry.row.querySelectorAll('.cc-recalc').forEach(function (item) {
                item.remove();
            });
        });

        var jobs = data.jobs;
        var next = 0;
        var done = 0;
        var total = jobs.reduce(function (sum, job) {
            return sum + job.test_ids.length;
        }, 0);

        function runNext() {
            progress.textContent = format(strings.progress, {done: done, total: total});
            if (next >= jobs.length) {
                finish();
                return;
            }
            runJob(jobs[next]).then(function (results) {
                done += results.length;
                results.forEach(function (result) {
                    var entry = entries[result.test_id];
                    if (!entry) {
                        return;
                    }
                    addResult(entry, result);
                    // Mirrors TestCheck.status: a test that couldn't be recalculated
                    // on one unit is fine if it was recalculated on another.
                    if (result.status !== 'not_run') {
                        entry.ran = true;
                        entry.statuses.push(result.severity);
                    }
                    setStatus(entry, worst(entry.statuses));
                });
                update();
                next += 1;
                runNext();
            });
        }

        function finish() {
            Object.keys(entries).forEach(function (id) {
                var entry = entries[id];
                if (!entry.ran) {
                    entry.statuses.push('not_run');
                    if (!entry.row.querySelector('.cc-recalc')) {
                        addNote(entry, strings.noResults);
                    }
                }
                setStatus(entry, worst(entry.statuses));
            });
            progress.textContent = format(strings.finished, {done: done, total: total});
            button.disabled = false;
            update();
        }

        runNext();
    }

    button.addEventListener('click', recalculate);
    problemsOnly.addEventListener('change', update);
    update();
})();
