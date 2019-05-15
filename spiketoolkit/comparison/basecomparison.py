import spikeextractors as se

from .comparisontools import (count_matching_events, compute_agreement_score,
                                                do_matching, do_score_labels, do_counting, do_confusion_matrix)


class BaseComparison:
    """
    Base class shared by SortingComparison and GroundTruthComparison
    
    """
    def __init__(self, sorting1, sorting2, sorting1_name=None, sorting2_name=None, delta_frames=10, min_accuracy=0.5,
                 count=False, n_jobs=1, verbose=False):
        self._sorting1 = sorting1
        self._sorting2 = sorting2
        self.sorting1_name = sorting1_name
        self.sorting2_name = sorting2_name
        self._delta_frames = delta_frames
        self._min_accuracy = min_accuracy
        self._n_jobs = n_jobs
        if verbose:
            print("Matching...")
        self._do_matching()

        self._mixed_counts = None
        if count:
            if verbose:
                print("Counting...")
            self._do_counting(verbose=verbose)

    def get_sorting1(self):
        # Samuel EDIT : why not a direct attribute acees  with self.sorting1 ?
        return self._sorting1

    def get_sorting2(self):
        # Samuel EDIT : why not a direct attribute acees  with self.sorting2 ?
        return self._sorting2
    
    def get_labels1(self, unit_id):
        if unit_id in self._sorting1.get_unit_ids():
            return self._labels_st1[unit_id]
        else:
            raise Exception("Unit_id is not a valid unit")

    def get_labels2(self, unit_id):
        if unit_id in self._sorting1.get_unit_ids():
            return self._labels_st1[unit_id]
        else:
            raise Exception("Unit_id is not a valid unit")


    def compute_counts(self):
        if self._mixed_counts is None:
            self._do_counting(verbose=False)


    def plot_confusion_matrix(self, xlabel=None, ylabel=None):
        # Samuel EDIT
        # This must be moved in spikewidget
        import matplotlib.pylab as plt

        if self._mixed_counts is None:
            self._do_counting(verbose=False)

        sorting1 = self._sorting1
        sorting2 = self._sorting2
        unit1_ids = sorting1.get_unit_ids()
        unit2_ids = sorting2.get_unit_ids()
        N1 = len(unit1_ids)
        N2 = len(unit2_ids)
        st1_idxs, st2_idxs = self._do_confusion()
        fig, ax = plt.subplots()
        # Using matshow here just because it sets the ticks up nicely. imshow is faster.
        ax.matshow(self._confusion_matrix, cmap='Greens')

        for (i, j), z in np.ndenumerate(self._confusion_matrix):
            if z != 0:
                if z > np.max(self._confusion_matrix) / 2.:
                    ax.text(j, i, '{:d}'.format(z), ha='center', va='center', color='white')
                else:
                    ax.text(j, i, '{:d}'.format(z), ha='center', va='center', color='black')

        ax.axhline(int(N1 - 1) + 0.5, color='black')
        ax.axvline(int(N2 - 1) + 0.5, color='black')

        # Major ticks
        ax.set_xticks(np.arange(0, N2 + 1))
        ax.set_yticks(np.arange(0, N1 + 1))
        ax.xaxis.tick_bottom()
        # Labels for major ticks
        ax.set_xticklabels(np.append(st2_idxs, 'FN'), fontsize=12)
        ax.set_yticklabels(np.append(st1_idxs, 'FP'), fontsize=12)

        if xlabel == None:
            if self.sorting2_name is None:
                ax.set_xlabel('Sorting 2', fontsize=15)
            else:
                ax.set_xlabel(self.sorting2_name, fontsize=15)
        else:
            ax.set_xlabel(xlabel, fontsize=20)
        if ylabel == None:
            if self.sorting1_name is None:
                ax.set_ylabel('Sorting 1', fontsize=15)
            else:
                ax.set_ylabel(self.sorting1_name, fontsize=15)
        else:
            ax.set_ylabel(ylabel, fontsize=20)

        return ax
    def _do_matching(self):
        self._event_counts_1,  self._event_counts_2, self._matching_event_counts_12,\
            self._best_match_units_12, self._matching_event_counts_21,\
            self._best_match_units_21,self._unit_map12,\
            self._unit_map21 = do_matching(self._sorting1, self._sorting2, self._delta_frames, self._min_accuracy, self._n_jobs)

    def _do_counting(self, verbose=False):
        self._labels_st1, self._labels_st2 = do_score_labels(self._sorting1, self._sorting2,
                                                             self._delta_frames, self._unit_map12)
        self._mixed_counts = do_counting(self._sorting1, self._sorting2, self._unit_map12,
                                         self._labels_st1, self._labels_st2)

    def _do_confusion(self):
        self._confusion_matrix,  st1_idxs, st2_idxs = do_confusion_matrix(self._sorting1, self._sorting2,
                                                self._unit_map12, self._labels_st1, self._labels_st2)

        return st1_idxs, st2_idxs
    

    