(function () {
  "use strict";

  var REFRESH_INTERVAL = 300000; // 5 minutes, matches core scoreboard polling
  var standings = [];

  var schoolSelect = document.getElementById("efe-school-filter");
  var classSelect = document.getElementById("efe-class-filter");
  var tbody = document.getElementById("efe-scoreboard-body");
  var emptyMessage = document.getElementById("efe-scoreboard-empty");

  if (!tbody) {
    return;
  }

  function escapeHtml(value) {
    var div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  }

  function uniqueSorted(values) {
    var seen = {};
    var result = [];
    values.forEach(function (v) {
      if (v && !seen[v]) {
        seen[v] = true;
        result.push(v);
      }
    });
    result.sort(function (a, b) {
      return a.localeCompare(b);
    });
    return result;
  }

  function populateFilter(select, values, previousValue) {
    var options = ['<option value="">All</option>'];
    values.forEach(function (v) {
      options.push(
        '<option value="' +
          escapeHtml(v) +
          '"' +
          (v === previousValue ? " selected" : "") +
          ">" +
          escapeHtml(v) +
          "</option>",
      );
    });
    select.innerHTML = options.join("");
  }

  // Only offer the classes that belong to the currently selected school.
  function populateClassFilter() {
    var school = schoolSelect.value;
    var classes = uniqueSorted(
      standings
        .filter(function (r) { return !school || r.school === school; })
        .map(function (r) { return r.student_class; }),
    );
    populateFilter(classSelect, classes, classSelect.value);
  }

  function render() {
    var school = schoolSelect.value;
    var studentClass = classSelect.value;

    var filtered = standings.filter(function (row) {
      if (school && row.school !== school) {
        return false;
      }
      if (studentClass && row.student_class !== studentClass) {
        return false;
      }
      return true;
    });

    if (filtered.length === 0) {
      tbody.innerHTML = "";
      emptyMessage.classList.remove("d-none");
      return;
    }
    emptyMessage.classList.add("d-none");

    var rows = filtered.map(function (row, index) {
      return (
        "<tr>" +
        '<th scope="row" class="text-center">' +
        (index + 1) +
        "</th>" +
        '<td class="text-start"><a href="' +
        escapeHtml(row.account_url) +
        '">' +
        escapeHtml(row.name) +
        "</a></td>" +
        "<td>" +
        escapeHtml(row.school) +
        "</td>" +
        "<td>" +
        escapeHtml(row.student_class) +
        "</td>" +
        "<td>" +
        row.score +
        "</td>" +
        "</tr>"
      );
    });
    tbody.innerHTML = rows.join("");
  }

  function update() {
    fetch("/plugins/enhanced_for_educate/scoreboard.json", {
      credentials: "same-origin",
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (json) {
        if (!json.success) {
          return;
        }
        standings = json.data;

        populateFilter(
          schoolSelect,
          uniqueSorted(standings.map(function (r) { return r.school; })),
          schoolSelect.value,
        );
        populateClassFilter();

        render();
      });
  }

  schoolSelect.addEventListener("change", function () {
    populateClassFilter();
    render();
  });
  classSelect.addEventListener("change", render);

  update();
  setInterval(update, REFRESH_INTERVAL);
})();
