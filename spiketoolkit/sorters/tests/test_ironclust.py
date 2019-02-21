import pytest
import spikeextractors as se
from spiketoolkit.sorters import IronclustSorter

from spiketoolkit.sorters.tests.common_tests import SorterCommonTestSuite

# This run several tests
@pytest.mark.skipif(not IronclustSorter.installed)
class IronclustCommonTestSuite(SorterCommonTestSuite):
    SorterCLass = IronclustSorter



if __name__ == '__main__':
    IronclustCommonTestSuite().test_on_toy()
    #~ IronclustCommonTestSuite().test_several_groups()
    
