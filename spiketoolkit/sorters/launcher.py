"""
Utils functions to launch several sorter on several recording in parralelle or not.
"""
import os
from pathlib import Path
import multiprocessing
import shutil
import json
import traceback

import spikeextractors as se

from .sorterlist import sorter_dict, run_sorter




def _run_one(arg_list):
    # the multiprocessing python module force to have one unique tuple argument
    rec_name, recording, sorter_name, output_folder,grouping_property, debug, params = arg_list
    try:
    #~ if True:
        SorterClass = sorter_dict[sorter_name]
        sorter = SorterClass(recording=recording, output_folder=output_folder, grouping_property=grouping_property,
                             parallel=True, debug=debug, delete_output_folder=False)
        sorter.set_params(**params)

        run_time = sorter.run()
        with open(output_folder / 'run_log.txt', mode='w') as f:
            f.write('run_time: {}\n'.format(run_time))
            
    except Exception as err:
        run_time = None
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        with open(output_folder / 'run_log.txt', mode='w') as f:
            f.write('*** ERROR IN SORTER ***\n\n')
            traceback.print_tb(err.__traceback__, file=f)


def copy_share_binary(working_folder, recording_dict, overwrite=False):
    """
    This copy inside a working_folder/raw_files all recording as
    BinDatRecordingExtractor
    """
    os.makedirs(working_folder / 'raw_files')
    old_rec_dict = dict(recording_dict)
    recording_dict = {}
    for rec_name, recording in old_rec_dict.items():
        
        raw_filename = working_folder / 'raw_files' / (rec_name+'.raw')
        prb_filename = working_folder / 'raw_files' / (rec_name+'.prb')
        json_filename = working_folder / 'raw_files' / (rec_name+'.json')
        num_chan = recording.get_num_channels()
        chunksize = 2**24// num_chan
        sr = recording.get_sampling_frequency()
        
        # save binary
        se.write_binary_dat_format(recording, raw_filename, time_axis=0, dtype='float32', chunksize=chunksize)
        # save location (with PRB format)
        se.save_probe_file(recording, prb_filename, format='spyking_circus')
        # save json info for binary format (for easy persistency)
        with open(json_filename, 'w', encoding='utf8') as f:
            info = dict(sample_rate=sr, num_chan=num_chan, dtype='float32', frames_first=True)
            json.dump(info, f, indent=4)
        
        # make new  recording
        new_rec = se.BinDatRecordingExtractor(raw_filename, sr, num_chan, 'float32', frames_first=True)
        se.load_probe_file(new_rec, prb_filename)
        recording_dict[rec_name] = new_rec
        
    return recording_dict
    

def run_sorters(sorter_list, recording_dict_or_list,  working_folder, sorter_params={}, grouping_property=None,
                            shared_binary_copy=False, mode='raise', engine=None, engine_kargs={}, debug=False):
    """
    This run several sorter on several recording.
    Simple implementation are nested loops or with multiprocessing.

    sorter_list: list of str (sorter names)
    recording_dict_or_list: a dict (or a list) of recording
    working_folder : str

    engine = None ( = 'loop') or 'multiprocessing'
    processes = only if 'multiprocessing' if None then processes=os.cpu_count()
    debug=True/False to control sorter verbosity

    Note: engine='multiprocessing' use the python multiprocessing module.
    This do not allow to have subprocess in subprocess.
    So sorter that already use internally multiprocessing, this will fail.

    Parameters
    ----------
    
    sorter_list: list of str
        List of sorter name.
    
    recording_dict_or_list: dict or list
        A dict of recording. The key will be the name of the recording.
        In a list is given then the name will be recording_0, recording_1, ...
    
    working_folder: str
        The working directory.
        This must not exists before calling this function.
    
    grouping_property: str
        The property of grouping given to sorters.
    
    sorter_params: dict of dict with sorter_name as key
        This allow to overwritte default params for sorter.
    
    shared_binary_copy: False default
        Before running each sorter, all recording are copied inside 
        the working_folder with the raw binary format (BinDatRecordingExtractor)
        and new recording are instantiated as BinDatRecordingExtractor.
        This avoids multiple copy inside each sorter of the same file but
        imply a global of all files.
    
    mode: 'raise_if_exists' or 'overwrite' or 'keep'
        The mode when the subfolder of recording/sorter already exists.
            * 'raise' : raise error if subfolder exists
            * 'overwrite' : force recompute
            * 'keep' : do not compute again if f=subfolder exists and log is OK

    engine: str
        'loop' or 'multiprocessing'
    
    engine_kargs: dict
        This contains kargs specific to the launcher engine:
            * 'loop' : no kargs
            * 'multiprocessing' : {'processes' : } number of processes
    
    debug: bool
        default True
    
    Output
    ----------
    
    results : dict
        The output is nested dict[rec_name][sorter_name] of SortingExtrator.

    """
    if mode == 'raise':
        assert not os.path.exists(working_folder), 'working_folder already exists, please remove it'
    working_folder = Path(working_folder)
    
    for sorter_name in sorter_list:
        assert sorter_name in sorter_dict, '{} is not in sorter list'.format(sorter_name)

    if isinstance(recording_dict_or_list, list):
        # in case of list
        recording_dict = { 'recording_{}'.format(i): rec for i, rec in enumerate(recording_dict_or_list) }
    elif isinstance(recording_dict_or_list, dict):
        recording_dict = recording_dict_or_list
    else:
        raise(ValueError('bad recording dict'))

    # when  grouping_property is not None : split in subrecording
    # but the subrecording must have len=1 because otherwise it break
    # the internal organisation of folder name.
    if grouping_property is not None:
        for rec_name, recording in recording_dict.items():
            recording_list = se.get_sub_extractors_by_property(recording, grouping_property)
            n_group = len(recording_list)
            assert n_group == 1, 'run_sorters() work only if grouping_property=None or if it split into one subrecording'
            recording_dict[rec_name] = recording_list[0]
        grouping_property = None
    
    if shared_binary_copy:
        recording_dict = copy_share_binary(working_folder, recording_dict, overwrite=(mode=='overwrite'))

    task_list = []
    for rec_name, recording in recording_dict.items():
        for sorter_name in sorter_list:
            output_folder = working_folder / 'output_folders' / rec_name / sorter_name

            if is_log_ok(output_folder):
                # check is output_folders exists
                if mode == 'raise':
                    raise(Exception('output folder already exists for {} {}'.format(rec_name, sorter_name)))
                elif mode == 'overwrite':
                    shutil.rmtree(str(output_folder))
                elif mode == 'keep':
                    continue
                else:
                    raise(ValueError('mode not in raise, overwrite, keep'))
            params = sorter_params.get(sorter_name, {})
            task_list.append((rec_name, recording, sorter_name, output_folder, grouping_property, debug, params))

    if engine is None or engine == 'loop':
        # simple loop in main process
        for arg_list in task_list:
            # print(arg_list)
            _run_one(arg_list)

    elif engine == 'multiprocessing':
        # use mp.Pool
        processes = engine_kargs.get('processes', None)
        pool = multiprocessing.Pool(processes)
        pool.map(_run_one, task_list)

    results  = collect_results(working_folder)
    return results


def is_log_ok(output_folder):
    # log is OK when run_time is not None
    if os.path.exists(output_folder / 'run_log.txt'):
        with open(output_folder / 'run_log.txt', mode='r') as logfile:
            line = logfile.readline()
            if 'run_time:' in line and 'ERROR' not in line:
                return True
    return False


def loop_over_folders(output_folders):
    for rec_name in os.listdir(output_folders):
        if not os.path.isdir(output_folders / rec_name):
            continue
        for sorter_name in os.listdir(output_folders / rec_name):
            output_folder = output_folders / rec_name / sorter_name
            if not os.path.isdir(output_folder):
                continue
            if not is_log_ok(output_folder):
                continue
            yield rec_name, sorter_name, output_folder
    

def collect_results(working_folder):
    """
    Collect results in a working_folder.

    The output is nested dict[rec_name][sorter_name] of SortingExtrator.
    """
    results = {}
    output_folders = Path(working_folder) / 'output_folders'
    
    for rec_name, sorter_name, output_folder in loop_over_folders(output_folders):
        if rec_name not in results:
            results[rec_name] = {}
        SorterClass = sorter_dict[sorter_name]
        results[rec_name][sorter_name] = SorterClass.get_result_from_folder(output_folder)
    return results

def collect_run_times(working_folder):
    """
    Collect run times in a working folder

    The output is list of (rec_name, sorter_name, run_time)
    """
    run_times = []
    output_folders = Path(working_folder) / 'output_folders'
    
    for rec_name, sorter_name, output_folder in loop_over_folders(output_folders):
        if os.path.exists(output_folder / 'run_log.txt'):
            with open(output_folder / 'run_log.txt', mode='r') as logfile:
                run_time = float(logfile.readline().replace('run_time:', ''))
            run_times.append((rec_name, sorter_name, run_time))
    return run_times



