<template>
  <div id="main" class="panel panel-default">
    <div class="panel-heading">
      <div>
        <i class="bi bi-clipboard-data"></i> Coverage Collection Browser
        <form
          class="form-inline pull-right"
          style="transform: translateY(-22%)"
        >
          <label for="rc_select">
            <i class="bi bi-funnel-fill"></i>
          </label>
          <select id="rc_select" class="form-control" @change="set_rc($event)">
            <option disabled selected value style="display: none">
              {{ rc_name }}
            </option>
            <option v-for="entry in rc_list" :key="entry.id" :value="entry.id">
              {{ entry.description }}
            </option>
          </select>
        </form>
      </div>
    </div>

    <template v-if="loading">
      <div class="loader"></div>
      <template v-if="loading_incomplete">
        <div class="loader-msg">
          <span>
            The requested collection is being processed by the server, please
            wait...
          </span>
        </div>
      </template>
    </template>
    <template v-else-if="source">
      <table class="table table-coverage">
        <tbody>
          <tr v-for="item in source" :key="item.idx">
            <td
              :id="item.idx"
              :class="['cov', 'cov-linenumber', item.lclass]"
              @click="line_click_handler(item.idx)"
            >
              {{ item.idx }}
            </td>
            <td :class="['cov', 'cov-occurence', item.lclass]">
              <span v-if="item.hits" class="label label-success">
                <!-- FIXME -->
                {{ formatNumber(item.hits) }}
              </span>
            </td>
            <td :class="['cov', 'cov-codeline', item.lclass]">
              <div v-html="highlight_code(item.line)"></div>
            </td>
          </tr>
        </tbody>
      </table>
    </template>
    <template v-else>
      <div v-show="search">
        <input ref="search" v-model="search" type="text" class="form-control" />
      </div>
      <line-chart v-if="chartdata" :chartdata="chartdata"></line-chart>
      <table class="table table-condensed table-hover table-db">
        <thead>
          <tr>
            <th
              style="width: 50%"
              :class="{ active: sortKey == 'name' }"
              @click="sortBy('name')"
            >
              Files
            </th>
            <th
              :class="{ active: sortKey == 'linesTotal' }"
              @click="sortBy('linesTotal')"
            >
              <span
                data-toggle="tooltip"
                data-placement="top"
                title="Tracked Lines"
              >
                <i class="bi bi-list"></i>
              </span>
            </th>
            <th
              :class="{ active: sortKey == 'linesCovered' }"
              @click="sortBy('linesCovered')"
            >
              Lines Covered
            </th>
            <th
              :class="{ active: sortKey == 'linesMissed' }"
              @click="sortBy('linesMissed')"
            >
              Lines Missed
            </th>
            <th
              :class="{ active: sortKey == 'coveragePercent' }"
              @click="sortBy('coveragePercent')"
            >
              Coverage
            </th>
            <th
              v-if="chartdata"
              :class="{ active: sortKey == 'delta_coveragePercent' }"
              @click="sortBy('delta_coveragePercent')"
            >
              Coverage Difference
            </th>
            <th
              v-if="chartdata"
              :class="{ active: sortKey == 'delta_linesCovered' }"
              @click="sortBy('delta_linesCovered')"
            >
              Lines Covered &Delta;
            </th>
            <th
              v-if="chartdata"
              :class="{ active: sortKey == 'delta_linesTotal' }"
              @click="sortBy('delta_linesTotal')"
            >
              Total Lines &Delta;
            </th>
          </tr>
          <tr v-if="show_top_nav">
            <td @click="navigate_top">
              <i class="bi bi-arrow-up"></i> <span class="path">..</span>
            </td>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(value, ordered_collection_path) in ordered_collection"
            :key="ordered_collection_path"
            @click="navigate(value)"
          >
            <td>
              <i :class="['bi', add_path_class(value)]"></i>
              &nbsp;
              <span :class="get_span_path_class(value)">{{ value.name }}</span>
            </td>
            <td>{{ formatNumber(value.linesTotal) }}</td>
            <td>{{ formatNumber(value.linesCovered) }}</td>
            <td>{{ formatNumber(value.linesMissed) }}</td>
            <td
              class="text-right"
              :style="cov_pct_style(value.coveragePercent)"
            >
              {{ value.coveragePercent }} %
            </td>
            <td
              v-if="chartdata"
              class="text-right"
              :style="cov_pct_style(value.delta_coveragePercent)"
            >
              {{ value.delta_coveragePercent }} %
            </td>
            <td v-if="chartdata" class="text-right">
              {{ value.delta_linesCovered }}
            </td>
            <td v-if="chartdata" class="text-right">
              {{ value.delta_linesTotal }}
            </td>
          </tr>
        </tbody>
        <tfoot v-show="!search" class="table-coverage-foot">
          <tr>
            <td><strong>Summary</strong></td>
            <td>{{ formatNumber(coverage.linesTotal) }}</td>
            <td>{{ formatNumber(coverage.linesCovered) }}</td>
            <td>{{ formatNumber(coverage.linesMissed) }}</td>
            <td
              class="text-right"
              :style="cov_pct_style(coverage.coveragePercent)"
            >
              {{ coverage.coveragePercent }} %
            </td>
            <td
              v-if="chartdata"
              class="text-right"
              :style="cov_pct_style(coverage.delta_coveragePercent)"
            >
              {{ coverage.delta_coveragePercent }} %
            </td>
            <td v-if="chartdata" class="text-right">
              {{ coverage.delta_linesCovered }}
            </td>
            <td v-if="chartdata" class="text-right">
              {{ coverage.delta_linesTotal }}
            </td>
          </tr>
        </tfoot>
      </table>
    </template>
  </div>
</template>
<script>
import _ from "lodash";
import Prism from "prismjs";
import swal from "sweetalert";
import { defineComponent } from "vue";
import {
  covManagerBrowseStats,
  covManagerDiffStats,
  reportMetadata,
  rvLists,
} from "../../api";
import { E_SERVER_ERROR, formatMonthly, formatQuarterly } from "../../helpers";
import { HashParamManager } from "../../params";
import "../../public/css/covmanager.css";
import LineChart from "./LineChart.vue";

export default defineComponent({
  components: {
    "line-chart": LineChart,
  },
  props: {
    diffApi: {
      type: Boolean,
      required: true,
    },
    collectionId: {
      type: Number,
      required: false,
    },
    ids: {
      type: Array,
      required: false,
      default: () => [],
    },
  },
  data() {
    let ISDIFF = false;
    let GETPARAMS = null;
    let COLLECTIONID = this.collectionId;

    if (this.diffApi) {
      ISDIFF = true;
      GETPARAMS = `ids=${this.ids.join(",")}`;
    }

    let pmanager = new HashParamManager();

    return {
      path: pmanager.get_value("p", ""),
      line: null,
      highlight_lines: { previous: [], current: [] },
      coverage: [],
      source: null,
      chart: null,
      chartdata: null,
      search: "",
      sortKey: "",
      reverse: false,
      show_top_nav: false,
      loading: false,
      loading_incomplete: false,
      last_line_clicked: null,
      line_click_timer: null,
      rc_dropdown: false,
      rc_name: "Report Configuration",
      rc_id: null,
      rc_list: [],
      storage_support: false,
      report_list: [],
      ISDIFF,
      GETPARAMS,
      COLLECTIONID,
      pmanager,
    };
  },
  computed: {
    current_path: function () {
      return this.path.split("/");
    },
    filtered_children: function () {
      let result = {};

      let children = this.coverage.children;

      if (!this.search) {
        return children;
      }

      const regex = new RegExp(this.search, "i");
      Object.keys(children).forEach((path) => {
        if (path.match(regex)) {
          result[path] = children[path];
        }
      });

      return result;
    },
    ordered_collection: function () {
      return _.orderBy(
        this.filtered_children,
        [this.sortKey],
        [this.reverse ? "desc" : "asc"],
      );
    },
  },
  watch: {
    path: "fetch",
    line: "scroll_to_line",
    highlight_lines: "change_highlighted_lines",
    rc_id: function () {
      this.update_rc_name();
      this.fetch();
    },
  },
  created() {
    window.addEventListener("keydown", this.keydown);
    window.addEventListener("keyup", this.keyup);
    window.addEventListener("hashchange", this.handleHashChange);

    // Check if local storage is available
    this.storage_support = this.test_storage_rc();

    this.rc_id = this.pmanager.get_value("rc", "");
    if (this.storage_support && this.rc_id === "") {
      this.rc_id = window.localStorage.getItem("covmanager_default_rc");

      // If we fetched a default rc value from local storage, then we
      // should always adjust the hash to match that, so the URL can be copied.
      if (this.rc_id != null) {
        this.pmanager.update_value("rc", this.rc_id);
        this.pmanager.update_hash();
      }
    }

    // Get the list of report configurations once at startup and cache it,
    // as it is unlikely to change while we are browsing the collection.
    this.get_rc_list().then(() => {
      this.update_rc_name();
    });
    this.fetch();
  },
  unmounted() {
    // Clean up event listeners
    window.removeEventListener("keydown", this.keydown);
    window.removeEventListener("keyup", this.keyup);
    window.removeEventListener("hashchange", this.handleHashChange);
  },
  updated() {
    let self = this;
    this.$nextTick(function () {
      // Once we updated the data, check for a line parameter and update the line
      // field accordingly if the value has changed. Updating the field will
      // trigger the scrolling function.
      let new_line = this.pmanager.get_value("s");
      if (self.line != new_line) {
        self.line = new_line;
      } else {
        // Force scroll update, as we have re-rendered the DOM
        self.scroll_to_line();
      }

      // Also check if we are supposed to highlight any lines.
      let hl = this.pmanager.get_value("hl", "");
      if (hl != "") {
        // We always store the current and the previous highlight state when
        // changing/updating it to ensure that we can undo the previous highlight
        // without iterating or re-rendering all lines.
        self.highlight_lines = {
          previous: self.highlight_lines.current,
          current: hl.split(","),
        };
      }
    });
  },
  methods: {
    apiParams: function () {
      let query_params = {};

      let ids = this.pmanager.get_value("ids");
      if (ids) {
        query_params["ids"] = ids;
      }

      let rc = this.pmanager.get_value("rc");
      if (rc) {
        query_params["rc"] = rc;
      }

      return query_params;
    },
    fetch: _.throttle(function () {
      this.loading = true;

      const requestConfig = {
        path: this.path,
        params: this.apiParams(),
        cb: () => {
          setTimeout(this.fetch, 1000);
          this.loading_incomplete = true;
        },
      };

      let apiRequest;
      if (this.diffApi) {
        apiRequest = covManagerDiffStats(requestConfig);
      } else {
        apiRequest = covManagerBrowseStats({
          ...requestConfig,
          id: this.collectionId,
        });
      }

      apiRequest
        .then((json) => {
          if (!json) {
            return;
          }

          this.coverage = json["coverage"];
          if ("source" in this.coverage) {
            let lsource = this.coverage["source"].split("\n");
            let psource = [];
            for (let i = 0; i < lsource.length; i++) {
              let lclass = "";
              let lhits = "";
              if (this.coverage.coverage[i] > 0) {
                lclass = "cov-status-covered";
                lhits = this.coverage.coverage[i];
              } else if (this.coverage.coverage[i] == 0) {
                lclass = "cov-status-non-coverable";
              }
              psource.push({
                line: lsource[i],
                lclass: lclass,
                hits: lhits,
                idx: i,
              });
            }

            this.source = psource;
          } else {
            this.source = null;
          }

          if ("ttdata" in json) {
            this.chartdata = {};
            this.chartdata["ids"] = [];
            this.chartdata["labels"] = [];
            this.chartdata["datasets"] = [
              {
                id: 1,
                label: "Total Coverage (%)",
                borderColor: "#f87979",
                fill: "false",
                pointRadius: 5,
                pointBackgroundColor: "#f87979",
                yAxisID: "y-axis-0",
                data: [],
                deltas: [],
                created: [],
                unit: "%",
              },
              {
                id: 2,
                label: "Lines not covered",
                borderColor: "#6699ff",
                fill: "false",
                pointRadius: 5,
                pointBackgroundColor: "#6699ff",
                yAxisID: "y-axis-1",
                data: [],
                deltas: [],
                created: [],
                unit: "lines",
              },
              {
                id: 3,
                label: "Total lines (coverable)",
                borderColor: "#ff9966",
                fill: "false",
                pointRadius: 5,
                pointBackgroundColor: "#ff9966",
                yAxisID: "y-axis-1",
                data: [],
                deltas: [],
                created: [],
                unit: "lines",
              },
            ];

            for (let i = 0; i < json["ttdata"].length; ++i) {
              this.chartdata["ids"].push(json["ttdata"][i]["id"]);
              this.chartdata["labels"].push(
                this.wrap_text(json["ttdata"][i]["label"], 10),
              );

              this.chartdata["datasets"][0]["data"].push(
                json["ttdata"][i]["coveragePercent"],
              );
              this.chartdata["datasets"][1]["data"].push(
                json["ttdata"][i]["linesMissed"],
              );
              this.chartdata["datasets"][2]["data"].push(
                json["ttdata"][i]["linesTotal"],
              );

              this.chartdata["datasets"][0]["created"].push(
                json["ttdata"][i]["created"],
              );
              if (i > 0) {
                this.chartdata["datasets"][0]["deltas"].push(
                  json["ttdata"][i]["delta_coveragePercent"],
                );
                this.chartdata["datasets"][1]["deltas"].push(
                  json["ttdata"][i]["delta_linesMissed"],
                );
                this.chartdata["datasets"][2]["deltas"].push(
                  json["ttdata"][i]["delta_linesTotal"],
                );
              }
            }
          }

          // (Re)fetch potential report metadata. This could be cached in the
          // future to only refetch if any of the ids actually change.
          this.get_report_metadata();

          this.loading = false;
          this.loading_incomplete = false;

          // If we have a path, then we need to show the top navigation link
          this.show_top_nav = !!this.path;

          // Start with an empty search after fetching new data
          this.search = "";
        })
        .catch(() => {
          swal("Oops", E_SERVER_ERROR, "error");
          this.loading = false;
          window.history.back();
        });
    }, 500),
    navigate: function (value) {
      if (this.chartdata && !("children" in value)) {
        // Block navigating to files if we are in diff mode
        return;
      }

      let location = value.name;
      this.pmanager.update_value(
        "p",
        this.path +
          (this.coverage.children[location]["children"]
            ? location + "/"
            : location),
      );
      this.pmanager.update_hash();
    },
    sortBy: function (sortKey) {
      this.reverse = this.sortKey === sortKey ? !this.reverse : false;
      this.sortKey = sortKey;
    },
    navigate_top: function () {
      let path_components = this.path.split("/");

      // Pop one non-empty component or stop when list is empty.
      while (path_components && !path_components.pop()) {
        //
      }

      this.pmanager.update_value("p", path_components.join("/") + "/");
      this.pmanager.update_hash();
    },
    get_report_metadata: function () {
      let ids = null;
      if (!this.ISDIFF) {
        // Not a diff view, fetch for a single id
        ids = this.COLLECTIONID;
      } else {
        ids = this.pmanager.get_value("ids");
        if (!ids) return;
      }

      return reportMetadata({ coverage__ids: ids })
        .then((json) => {
          this.report_list = json["results"];

          function compute_report_description(report) {
            if (report.is_quarterly) {
              report.description =
                "Quarterly Report - " + formatQuarterly(report.data_created);
            } else if (report.is_monthly) {
              report.description =
                "Monthly Report - " + formatMonthly(report.data_created);
            } else {
              report.description = "Weekly Report";
            }

            return report;
          }

          if (!this.ISDIFF && this.report_list) {
            let report = this.report_list[0];
            if (report) {
              report = compute_report_description(report);
              document.title = `${report.description} - CovManager`;
            }
          } else {
            for (let i = 0; i < this.chartdata["ids"].length; ++i) {
              for (let report of this.report_list) {
                if (report["coverage"] == this.chartdata["ids"][i]) {
                  compute_report_description(report);
                  this.chartdata["labels"][i] = this.wrap_text(
                    report.description,
                    10,
                  );
                  break;
                }
              }
            }
          }
        })
        .catch(() => {
          swal("Oops", E_SERVER_ERROR, "error");
        });
    },
    get_rc_list: function () {
      return rvLists({ __exclude: "directives" })
        .then((json) => {
          this.rc_list = json["results"];

          this.rc_list.sort(function (a, b) {
            let da = a.description.toLowerCase();
            let db = b.description.toLowerCase();
            if (da < db) return -1;
            if (da > db) return 1;
            return 0;
          });
        })
        .catch(() => {
          swal("Oops", E_SERVER_ERROR, "error");
        });
    },
    set_rc: function (event) {
      const id = event.target.options[event.target.options.selectedIndex].value;
      this.pmanager.update_value("rc", id);
      this.pmanager.update_hash();

      if (this.storage_support) {
        window.localStorage.setItem("covmanager_default_rc", id);
      }
    },
    clear_rc: function () {
      this.pmanager.update_value("rc", "");
      this.pmanager.update_hash();
      this.rc_id = "";

      if (this.storage_support) {
        window.localStorage.removeItem("covmanager_default_rc");
      }
    },
    test_storage_rc: function () {
      try {
        localStorage.setItem("covmanager_storage_test", "test");
        localStorage.removeItem("covmanager_storage_test");
      } catch (e) {
        return false;
      }
      return true;
    },
    update_rc_name: function () {
      for (let rc of this.rc_list) {
        if (rc["id"] == this.rc_id) {
          this.rc_name = rc["description"];
          return;
        }
      }
      this.rc_name = "Report Configuration";

      if (this.rc_id && this.rc_list.length > 0) {
        // Apparently there is an rc id set, but it is not in our list.
        // This could mean that we have a delected rc id at hand, which
        // might even be stored in local storage. Hence we should invalidate
        // at least local storage.
        if (this.storage_support) {
          window.localStorage.removeItem("covmanager_default_rc");
        }
      }
    },
    cov_pct_style: function (pct) {
      // Todo: Add to a CSS class.
      let status_color;
      if (pct === 100.0) {
        status_color = "#edfde7";
      } else if (pct >= 80.0) {
        status_color = "#fafde8";
      } else {
        status_color = "#fbece9";
      }
      return `background: linear-gradient(90deg, ${status_color} ${pct}%, white ${pct}%)`;
    },
    cov_hits: function (i) {
      return this.coverage.coverage[i] > 0 ? this.coverage.coverage[i] : "";
    },
    add_coverage_status_class: function (i) {
      let classArray = [];
      if (this.coverage.coverage[i] > 0) {
        // Line is covered.
        classArray.push("cov-status-covered");
      } else if (this.coverage.coverage[i] == 0) {
        // Line is coverable but was not covered.
        classArray.push("cov-status-non-coverable");
      } else {
        // Line is not coverable.
      }
      return classArray;
    },
    add_path_class: function (value) {
      let classArray = "class" in this ? this.class.split(" ") : [];
      if ("children" in value) {
        classArray.push("bi-folder");
      } else {
        classArray.push("bi-file-earmark");
      }
      return classArray;
    },
    get_span_path_class: function (value) {
      // If we are in diff mode (we have chart data), then we don't want to show file paths as clickable.
      if (!this.chartdata || "children" in value) {
        return "path";
      }
      return "";
    },
    highlight_code: function (code) {
      return Prism.highlight(code, Prism.languages.clike);
    },
    wrap_text: function (text, maxlen) {
      let textParts = text.split(" ");
      let result = [];
      let lastIdx = -1;

      for (const element of textParts) {
        if (
          lastIdx >= 0 &&
          result[lastIdx].length + element.length + 1 <= maxlen
        ) {
          result[lastIdx] += " " + element;
        } else {
          result.push(element);
          lastIdx++;
        }
      }
      return result;
    },
    scroll_to_line: function () {
      if (this.line != null) {
        let target = document.getElementById(this.line);
        if (target) {
          let target_offset = target.offsetTop;
          let height = target.height;
          let window_height = window.innerHeight;
          let offset;

          if (height < window_height) {
            offset = target_offset - (window_height / 2 - height / 2);
          } else {
            offset = target_offset;
          }
          document.documentElement.animate({ scrollTop: offset }, 700);
        }
      } else {
        window.scroll(0, 0);
      }
    },
    change_highlighted_lines: function () {
      function toggle(line, state) {
        let lines = [];
        if (line.indexOf("-") > 0) {
          let start_end = line.split("-");
          for (let i = start_end[0]; i <= start_end[1]; ++i) {
            lines.push(i);
          }
        } else {
          lines = [line];
        }

        for (const element of lines) {
          if (element != "") {
            let target = document.getElementById(element);
            if (target) target.classList.toggle("cov-line-highlighted", state);
          }
        }
      }

      for (const element of this.highlight_lines.previous) {
        toggle(element, false);
      }

      for (const element of this.highlight_lines.current) {
        toggle(element, true);
      }
    },
    line_click_handler: function (line) {
      // Handling click and double click on the same element as different events
      // without overlapping them is not possible. We therefore need to emulate
      // double click handling ourselves by using a timer.
      let self = this;
      if (self.last_line_clicked == line) {
        clearTimeout(self.line_click_timer);
        self.last_line_clicked = null;
        self.toggle_highlight_line(line);
      } else {
        self.last_line_clicked = line;
        self.line_click_timer = setTimeout(function () {
          self.last_line_clicked = null;
          self.set_scroll_line(line);
        }, 300);
      }
    },
    set_scroll_line: function (line) {
      this.pmanager.update_value("s", line);
      this.pmanager.update_hash();
    },
    toggle_highlight_line: function (line) {
      // This method is a bit lenghty because we need to first destructure the
      // existing parameters in the URL, then toggle, then restructure them
      // to update the hash. Updating the hash also updates the internal
      // properties of the model and does the actual highlight.

      // Get the current hl parameters from hash
      let hl = this.pmanager.get_value("hl", "");

      // Transform these into a set of lines highlighted
      let lines = {};
      let hl_parts = [];
      if (hl != "") {
        hl_parts = hl.split(",");
      }
      hl_parts.forEach(function (hl_part) {
        if (hl_part.indexOf("-") > 0) {
          let start_end = hl_part.split("-");
          for (let i = start_end[0]; i <= start_end[1]; ++i) {
            lines[i] = true;
          }
        } else {
          lines[hl_part] = true;
        }
      });

      // Do the actual toggle
      if (lines[line]) {
        delete lines[line];
      } else {
        lines[line] = true;
      }

      // Turn the set into a sorted array for iterating
      let sorted_lines = Object.keys(lines).sort((a, b) => a - b);
      let new_hl_parts = [];

      let range_start = -1;
      let last_line = -1;

      // The next loop has a lookahead of 1 to build ranges. By adding one
      // dummy element at the end, we can avoid some code duplication here
      // and the function properly finishes the last line/range.
      sorted_lines.push(-1);
      sorted_lines.forEach(function (sorted_line) {
        if (last_line >= 0) {
          if (last_line != sorted_line - 1) {
            if (range_start === last_line) {
              /* Single line to add */
              new_hl_parts.push(last_line);
            } else {
              /* Add a range from range_start to last_line */
              new_hl_parts.push(range_start + "-" + last_line);
            }
            range_start = sorted_line;
          }
        } else {
          range_start = sorted_line;
        }
        last_line = sorted_line;
      });

      this.pmanager.update_value("hl", new_hl_parts.join(","));
      this.pmanager.update_hash();
    },
    keydown: function (e) {
      if (!e) {
        e = window.event;
      }

      // Ignore the keypress if any of these modifiers are active
      if (
        e.getModifierState("Fn") ||
        e.getModifierState("OS") ||
        e.getModifierState("Win") ||
        e.getModifierState("Control") ||
        e.getModifierState("Alt") ||
        e.getModifierState("Meta")
      ) {
        return;
      }

      if (!e.metaKey) {
        if (
          (e.keyCode >= 65 && e.keyCode <= 90) ||
          (e.keyCode >= 48 && e.keyCode <= 57)
        ) {
          if (!this.search) {
            let str = String.fromCharCode(e.keyCode);
            if (!e.shiftKey) {
              str = str.toLowerCase();
            }
            this.search = str;
          } else {
            this.$refs.search.focus();
          }
        } else if (e.keyCode === 13) {
          // ENTER was pressed, navigate
          let target = Object.keys(this.filtered_children)[0];
          if (target) {
            this.navigate(this.filtered_children[target]);
          }
        }
      }
    },
    keyup: function (e) {
      // We use the |keyup| event instead of |keydown| here in order to not collide with Vue's internal updating of
      // the search model on input events.
      if (!e) {
        e = window.event;
      }
      if (!e.metaKey) {
        if (this.search && e.keyCode === 27) {
          // ESC was pressed, clear search.
          this.search = "";
        }
      }
    },
    formatNumber: function (v) {
      if (Number.isInteger(v)) {
        return parseInt(v).toLocaleString();
      }
    },
    handleHashChange() {
      this.pmanager.update_state();

      let new_rc = this.pmanager.get_value("rc", "");
      if (this.rc_id != new_rc) {
        // If the report configuration id has changed, update it in the model.
        // This will also trigger an update for the displayed name.
        this.rc_id = new_rc;
      }

      let new_path = this.pmanager.get_value("p", "");
      let new_line = this.pmanager.get_value("s", null);

      let new_hl_lines = [];
      let hl = this.pmanager.get_value("hl", "");
      if (hl != "") {
        new_hl_lines = hl.split(",");
      }

      // Prevent reloads when the path hasn't changed
      if (this.path != new_path) {
        // If the path has changed, we can ignore the line part of the hash, as it
        // will be stored in the .updated() function of the Vue once our data is
        // loaded and rendered.
        this.path = new_path;
      } else {
        if (this.line != new_line) {
          // Scroll to the line only when the path hasn't changed. This happens when
          // the user manually changes or clears the line part of the hash.
          this.line = new_line;
        }

        this.highlight_lines = {
          previous: this.highlight_lines.current,
          current: new_hl_lines,
        };
      }
    },
  },
});
</script>
