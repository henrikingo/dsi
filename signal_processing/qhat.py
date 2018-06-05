from __future__ import print_function

from contextlib import contextmanager
import copy
import itertools
import numpy
import random

from matplotlib.ticker import FuncFormatter, MaxNLocator

DEFAULT_FIGIZE = (18, 8)


# QHat's definition requires it to permute change-windows
# which leads to non-determinism: we need to always get the
# same change-point results when running on the same input.
@contextmanager
def deterministic_random(seed):
    """
    Call random.seed(seed) during invocation and then restore state after.
    :param seed: RNG seed
    """
    state = random.getstate()
    random.seed(seed)
    try:
        yield
    finally:
        random.setstate(state)


class QHat(object):
    KEYS = ('index', 'value', 'value_to_avg', 'value_to_avg_diff', 'average', 'average_diff',
            'window_size', 'probability', 'revision', 'algorithm', 'order_of_changepoint', 'order',
            'create_time')

    def __init__(self, state, pvalue=None, permutations=None, online=None, threshold=None):
        self.state = state
        self.series = self.state.get('series', None)
        self.revisions = self.state.get('revisions', None)
        self.orders = self.state.get('orders', None)
        self.testname = self.state.get('testname', None)
        self.threads = self.state.get('threads', None)
        self.create_times = self.state.get('create_times', None)

        self._id = self.state.get('_id', None)

        _ = threshold

        self._change_points = state.get('change_points', None)
        self.pvalue = 0.05 if pvalue is None else pvalue
        self.permutations = 100 if permutations is None else permutations
        self.online = 20 if online is None else online
        self._windows = state.get('windows', None)
        self._min_change = state.get('min_change', None)
        self._max_q = state.get('max_q', None)
        self._min_change = state.get('min_change', None)
        self.dates = state.get('dates', None)

    def extract_q(self, qs):
        """
        Given an ordered sequence of Q-Hat values, output the max value and index

        :param list qs: qhat values
        :return: list (max , index, etc)
        """
        if qs:
            max_q_index = numpy.argmax(qs)
            # noinspection PyTypeChecker
            max_q = qs[max_q_index]
        else:
            max_q = 0
            max_q_index = 0

        return [
            max_q_index, max_q, max_q / self.average_value, max_q / self.average_diff,
            self.average_value, self.average_diff, self.t
        ]

    # Implementing change-point detection algorithm from https://arxiv.org/pdf/1306.4933.pdf
    def qs(self, series):
        """
        Find Q-Hat values for all candidate change points

        :param list series: the points to process
        :return:
        """
        t = len(series)
        self.t = t
        if t < 5:
            # Average value and average diff are used even when there is no data. This avoids an error.
            self.average_value = 1
            self.average_diff = 1
            return [0] * t
        n = 2
        m = t - n
        qs = [0, 0]  # represents q when n = 0, 1
        # The following line could safely replace the next 6 lines
        # diffs = [[abs(series[i] - series[j]) for i in range(t)] for j in range(t)]
        diffs = [None] * t
        for i in range(t):
            diffs[i] = [0] * t
        for i in range(t):
            for j in range(t):
                diffs[i][j] = abs(series[i] - series[j])

        term1 = 0.0  # sum i:0-n, j:n-t, diffs[i][j]
        term2 = 0.0  # sum i:0-n, k:(i+1)-n, diffs[i][k]
        term3 = 0.0  # sum j:n-t, k:(j+i)-t, diffs[j][k]

        # Normalization constants
        self.average_value = numpy.average(series)
        # I'm sure there's a better way than this next line, but it works for now
        self.average_diff = numpy.average(list(itertools.chain(*diffs)))
        # term1 = sum(diffs[i][j] for i in range(n) for j in range(n,t))
        for i in range(n):
            for j in range(n, t):
                term1 += diffs[i][j]
        # term2 = sum(diffs[i][k] for i in range(n) for k in range(i+1,n))
        for i in range(n):
            for k in range((i + 1), n):
                term2 += diffs[i][k]
        # term3 = sum(diffs[j][k] for j in range(n, t) for k in range(j+1,t))
        for j in range(n, t):
            for k in range((j + 1), t):
                term3 += diffs[j][k]

        term1_reg = term1 * (2.0 / (m * n))
        term2_reg = term2 * (2.0 / (n * (n - 1)))
        term3_reg = term3 * (2.0 / (m * (m - 1)))
        newq = (m * n / (m + n)) * (term1_reg - term2_reg - term3_reg)
        qs.append(newq)

        for x in range(3, (t - 2)):
            n += 1
            m = t - n

            # update term 1
            for y in range(n - 1):
                term1 -= diffs[n - 1][y]
            for y in range(n, t):
                term1 += diffs[y][n - 1]

            # update term 2
            for y in range(n - 1):
                term2 += diffs[n - 1][y]

            # update term 3
            for y in range((n + 1), t):
                term3 -= diffs[y][n]

            term1_reg = term1 * (2.0 / (m * n))
            term2_reg = term2 * (2.0 / (n * (n - 1)))
            term3_reg = term3 * (2.0 / (m * (m - 1)))
            newq = (m * n / (m + n)) * (term1_reg - term2_reg - term3_reg)

            qs.append(newq)

        qs.append(0)
        qs.append(0)
        return qs

    @property
    def change_points(self, seed=1234):
        with deterministic_random(seed):
            return self._compute_change_points()

    def _compute_change_points(self):
        if self._change_points is None:
            windows = []
            pts = len(self.series)
            qs = self.qs(self.series)
            first_q = self.extract_q(qs)
            max_q_index, max_q = first_q[0], first_q[1]
            min_change = max_q
            change_points = []

            # HIERARCHICALLY COMPUTE OTHER CHANGEPOINTS
            terminated = False
            while not terminated:
                candidates = []
                windows = [0] + sorted([c[0] for c in change_points]) + [pts]
                for i in range(len(windows) - 1):
                    window = self.series[windows[i]:windows[i + 1]]
                    win_qs = self.qs(window)
                    win_max = self.extract_q(win_qs)
                    win_max[0] += windows[i]

                    candidates.append(win_max)
                candidates.sort(key=lambda tup: tup[1])
                candidate_q = candidates[len(candidates) - 1][1]

                # RANDOMLY PERMUTE CLUSTERS FOR SIGNIFICANCE TEST

                above = 0.0  # results from permuted test >= candidate_q
                for i in range(self.permutations):
                    permute_candidates = []
                    for j in range(len(windows) - 1):
                        window = copy.copy(self.series[windows[j]:windows[j + 1]])
                        random.shuffle(window)
                        win_qs = self.qs(window)
                        win_max = self.extract_q(win_qs)
                        win_max = (win_max[0] + windows[j], win_max[1])
                        permute_candidates.append(win_max)
                    permute_candidates.sort(key=lambda tup: tup[1])
                    permute_q = permute_candidates[len(permute_candidates) - 1][1]
                    if permute_q >= candidate_q:
                        above += 1

                # for coloring the lines, we will use the first INSIGNIFICANT point
                # as our baseline for transparency
                if candidate_q < min_change:
                    min_change = candidate_q

                probability = above / (self.permutations + 1)
                if probability > self.pvalue:
                    terminated = True
                else:
                    change_points.append(list(candidates[len(candidates) - 1]) + [probability])

            self._change_points = self.add_to_change_points(change_points, 'qhat', QHat.KEYS)

            self._windows = windows
            self._min_change = min_change
            self._max_q = max_q
        return self._change_points

    def add_to_change_points(self, change_points, algorithm, keys):
        points = []
        i = 0
        for change_pt in change_points:
            index = change_pt[0]
            revision = self.revisions[index]
            order = self.orders[index]
            create_time = self.create_times[index]
            values = change_pt + [revision, algorithm, i, order, create_time]
            points.append(dict(zip(keys, values)))
            i += 1
        return points

    @property
    def windows(self):
        if self._windows is None:
            _ = self.change_points
        return self._windows

    @property
    def min_change(self):
        if self._min_change is None:
            _ = self.change_points
        return self._min_change

    @property
    def max_q(self):
        if self._max_q is None:
            _ = self.change_points
        return self._max_q

    def render(self, axes=None):
        import matplotlib.pyplot as plt
        flag_new = False
        pts = len(self.series)
        sort_pts = sorted(self.series)
        lowbound = sort_pts[0] * 0.9
        hibound = sort_pts[len(sort_pts) - 1] * 1.1
        xvals = [i for i in range(pts)]

        windows = self.windows
        if windows[len(windows) - 1] - windows[len(windows) - 2] > self.online + 1:
            current_dist = sorted(windows[len(windows) - (self.online + 1):len(windows) - 1])
            new_pt = windows[len(windows) - 1]
            min_end = current_dist[0]
            max_end = current_dist[len(current_dist) - 1]
            if new_pt < min_end or new_pt > max_end:
                flag_new = True

        def format_fn(tick_val, tick_pos):
            if int(tick_val) < len(self.revisions):
                i = int(tick_val)
                tick_str = self.revisions[i][0:7]
                if self.dates and i < len(self.dates):
                    tick_str = tick_str + '\n' + self.dates[i].strftime("%H:%M %Y/%m/%d")
            else:
                tick_str = ''
            return tick_str

        title = "{name} ({threads}) : {algorithm}".format(
            name=self.testname, threads=self.threads if self.threads else 'max', algorithm="qhat")

        # always create 1 subplot so that the rest of the code is shared
        if not axes:
            plt.figure(figsize=(DEFAULT_FIGIZE[0], DEFAULT_FIGIZE[1] / 2))
            axes = plt.subplot(1, 1, 1)

        axes.set_title(title, size=16)
        axes.set_ylabel('ops per sec')
        axes.axis([0, pts, lowbound, hibound])

        axes.xaxis.set_major_formatter(FuncFormatter(format_fn))
        axes.xaxis.set_major_locator(MaxNLocator(integer=True))

        for tick in axes.get_xticklabels():
            tick.set_visible(True)

        # DRAW GRAPH
        for c in self.change_points:
            # fake probabilities while we investigate
            # p = (c[1] - self.min_change) / (self.max_q - self.min_change)
            # print(p)
            # diff to min_value sets color
            diff = (self.max_q - self.min_change)
            if not diff:
                diff = 1
            cval = format(255 - min(255, int((c['value'] - self.min_change) / diff * 255)), '02x')
            cstring = '#ff' + cval + cval
            axes.axvline(x=c['index'], color=cstring, label=c['revision'])
        if flag_new and self.series:
            axes.axvline(x=pts - 1, color='r', linewidth=2, label=self.revisions[pts - 1])

        axes.plot(xvals, self.series, 'b-')
        axes.legend(loc="upper right")
        return plt

    def save(self, collection):
        self.state['change_points'] = self.change_points
        self.state['windows'] = self.windows
        self.state['online'] = self.online
        self.state['min_change'] = self.min_change
        self.state['max_q'] = self.max_q
        self.state['min_change'] = self.min_change
        # TODO: encapsulate
