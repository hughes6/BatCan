'''
  Driver - driver script to run multiple MPM simulations
'''
import yaml
import os
import matplotlib.pyplot as plt
import matplotlib as mpl
import pandas as pd
import numpy as np
import shutil
import itertools
from bat_can import bat_can

#========================================#
#               INPUTS                   #
#========================================#
#------CHANGING SIMULATION-------#
# MW - for specific capacity
density_anode = 3.48*1e6 # g/m^3
density_cathode = 3.48*1e6 # g/m^3

input_file = 'LFP_MPM.yaml'


#-CHANGING SIMULATION PARAMETERS-#
# MPM param list must be a dict with radii and volume fractions 
param_list = {"r_p": [[4e-7]], "eps_solid": [[0.65]]}

# graphing feature
colors = itertools.cycle(plt.rcParams['axes.prop_cycle'].by_key()['color'])



#========================================#
#   RUNS ALL SIMULATIONS, + SAVES DATA   #
#========================================#
# cores - number of cores used to run bat_can in parallel
# param_list - parameters to be changed in input file
# structure - anode, cathode, or sep where changes will occur
# output_dir - name of dir where csv files will be stored
# input_file - name of file to be ran in simulation
def bat_can_loop(cores, param_list, structure = None, output_dir = None, input_file = None):
    # Defalt output directory
    if output_dir is None:
      output_dir = 'driver'

    # Give user option to delete output directory and its contents if already exists
    if os.path.exists(output_dir):
      answer = input(f"Would you like to delete the contents of {output_dir}? \n")
      yes = ['y','Y','yes','YES','Yes']
      if answer in yes:
        for file in os.listdir(output_dir):
          filepath = os.path.join(output_dir,file)
          os.remove(filepath)
        shutil.rmtree(output_dir, ignore_errors=True)  # Deletes the directory, represses errorpo
      else:
        raise ValueError(f"Output directory: {output_dir} cannot be overwritten without permission")
    
    # Default input file and structure
    if input_file is None:
        input_file='mpm_porous_LCO.yaml'
    if structure is None:
        structure = 'anode'
    
    # File that will be passed to simulations
    base_file_path = 'inputs/'+input_file
    base_file = base_file_path[7:] 

    print(f"\n Running {len(param_list['r_p'])} simulations with {base_file}")

    # Check for equal number of particles and volume fractions
    if input_file == "mpm_porous_LCO.yaml":
        if len(param_list["r_p"]) != len(param_list["eps_solid"]):
          raise ValueError("Must have equal r_p and eps_solid parameters")

    # Save local copy of o.g. yaml file
    with open(base_file_path, 'r', encoding='utf-8') as master_yaml:
            master_data = yaml.safe_load(master_yaml)

    # Creates new yaml file for each run 
    # Then passes that file to bat_can and saves results in common dir
    for i in range(len(param_list["r_p"])):
        # Open dummy file and make changes
        with open(base_file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        data["cell-description"][structure]["r_p"] = param_list["r_p"][i]
        data["cell-description"][structure]["eps_solid"] = param_list["eps_solid"][i]
        for sim in data["parameters"]["simulations"]:
            if "outputs" in sim:
                sim["outputs"]["save-name"] = f"data_file_{i}"
        # Commit dummy file changes to actual yaml file
        with open(base_file_path, 'w', encoding='utf-8') as f:
            yaml.dump(data,f)

        print(f"\n Running iteration {i+1} with r_p: {param_list['r_p'][i]}, eps_solid: {param_list['eps_solid'][i]} \n")  
        
        bat_can(base_file, cores, driver=True, output_dir=output_dir)

    # Convert back to o.g. yaml file
    with open(base_file_path, 'w', encoding='utf-8') as file:
      yaml.dump(master_data,file)

 

#========================================#
#       PROCESSING DATA FOR MPM          #
#========================================#
# file_path - output_dir output files stored in, ex: driver
def process_mpm_data(file_path,param_list,structure=None):
  print('process entered')
  if structure is None:
    structure = 'anode'
  radii = param_list['r_p']
  radii_copy = radii
  param_list_copy=[]
  for i in range(len(radii)):
     param_list_copy.append(radii[i])
  avg_radii = [] 
  # Find avg particle radii for graph legend
  for row in radii:
    avg_radii.append(sum(row) / len(row))

  yaml_files = [f for f in os.listdir(file_path) if f.endswith('.yaml')]
  yaml_files.sort()

  thickness_anode = []
  thickness_cathode = []
  eps_solid_anode = []
  eps_solid_cathode =[]

  i=-1
  # get data from yaml files
  cathode_is_mpm = True
  anode_is_mpm = True
  for file in yaml_files:
    i+=1
    file = str(file_path) + str(file)
    with open(file, 'r') as f:
      cell_config = yaml.safe_load(f)
    if cell_config['cell-description']['cathode']['class'] != 'mpm':
      cathode_is_mpm = False
    if cell_config['cell-description']['anode']['class'] != 'mpm':
      anode_is_mpm = False
    if anode_is_mpm:
      thickness_anode.append(float(cell_config['cell-description']['anode']['thickness']))
      eps_solid_anode.append(cell_config['cell-description']['anode']['eps_solid'][i])
    if cathode_is_mpm:
      thickness_cathode.append(float(cell_config['cell-description']['cathode']['thickness']))
      #FIX THIS
      eps_solid_cathode.append(cell_config['cell-description']['cathode']['eps_solid'][0])

  # Local copy of pck files sorted so radii name matches
  pkl_files = [f for f in os.listdir(file_path) if f.endswith('.pkl')]
  pkl_files.sort()

  plt.figure(figsize=(6,4))

  # Plotting
  i=-1
  for file in pkl_files:
    i+=1
    file = str(file_path) + str(file)
    solution_df = pd.read_pickle(file)
    solution = solution_df.reset_index().to_numpy().T

    # Name for legend
    print(avg_radii, i )
    rad_name = f'avg r = {avg_radii[i]}'

    # Get voltage index
    phi_ed_indices = np.where(solution_df.columns == "phi_ed")[0]
    phi_ptr = 1 + phi_ed_indices[-1]

    # plotting
    color = next(colors)
    for j in range(int(solution[1, -1])): 
      # only plot charge discharge of cycle 3, makes it look better
      if j not in [2,3]:
        continue
      cycle = solution_df[solution_df.iloc[:, 0] == j + 1]
      t_0 = cycle.index[0]
      if j == 2:
        plt.plot(0.1 * (cycle.index - t_0) * abs(cycle.iloc[:, 1]) / 3600, cycle.iloc[:, phi_ptr - 1],label=f"{rad_name}",color=color)
      else:
        plt.plot(0.1 * (cycle.index - t_0) * abs(cycle.iloc[:, 1]) / 3600, cycle.iloc[:, phi_ptr - 1], label=None, color=color)
    
  figname = str(file_path) + 'V - capacity plot'
  plt.xlabel("Capacity (mAh/cm²)")
  plt.ylabel("Cell Potential (V)")
  plt.legend(
    loc='upper left',
    bbox_to_anchor=(1.05, 1),
    fontsize='x-small',
    ncol=1,
    frameon=True
  )
  plt.title("Voltage vs. Capacity for Multiple Simulations")
  plt.tight_layout()
  plt.savefig(figname)
  plt.show()
  plt.clf()

  rad_list = radii_copy
  for i in range(len(radii_copy)):
     rad_list[i] = len(rad_list[i])
  mass_loading_list = []
  cycles = []
  # cycles ^ just makes plots look better, shown in plotting below
  for file in pkl_files:
    file = str(file_path) + str(file)
    soluiton_df = pd.read_pickle(file)
    solution = solution_df.reset_index().to_numpy().T
    for j in range(int(solution[1,-1])):
      cycles.append(j)

  cmap = plt.get_cmap('plasma')
  ndata = 12
  color_ind = np.linspace(0,1,ndata)
  plt_colors = list()
  # color gradient
  for i in np.arange(ndata):
    plt_colors.append(cmap(color_ind[i]))
  i=-1
  # second plot for mass basis
  for file in pkl_files:
    i+=1
    file = str(file_path) + str(file)
    solution_df = pd.read_pickle(file)
    solution = solution_df.reset_index().to_numpy().T

    rad_name = f'avg r = {avg_radii[i]}'

    phi_ed_indices = np.where(solution_df.columns == "phi_ed")[0]
    phi_ptr = 1 + phi_ed_indices[-1]
 
    # mass_loading_anode =  density_anode * eps_solid_anode[i] * thickness_anode[i]
    mass_loading_cathode = density_cathode * eps_solid_cathode[i] * thickness_cathode[i] * 0.0001
    mass_loading_cathode = mass_loading_cathode*rad_list[i] # this gets rid of overcounting for many particles
    # print('mass loading an ', mass_loading_anode)
    print('mass loading ca', mass_loading_cathode)
    # mass_loading_list.append(mass_loading_anode + mass_loading_cathode)
    mass_loading_list.append(mass_loading_cathode)


  
    for j in range(int(solution[1,-1])):
      # This makes plots look better, it is taking charge discahrge of cycle 3
      if j not in [2,3]:
        continue
      cycle = solution_df[solution_df.iloc[:, 0] == j + 1]
      t_0 = cycle.index[0]
      capacity_mAhcm2 = 0.1 * (cycle.index - t_0) * abs(cycle.iloc[:, 1]) / 3600
      capacity_mAhg = capacity_mAhcm2 / mass_loading_list[0] 
      if j == 2:
        plt.plot(capacity_mAhg, cycle.iloc[:, phi_ptr - 1], label=f"{rad_name}",color=plt_colors[i+1])
      else:
        plt.plot(capacity_mAhg, cycle.iloc[:, phi_ptr - 1], label=None,color=plt_colors[i+1])
  figname = str(file_path) + 'V - capacity plot mass basis'
  plt.xlabel("Capacity (mAh/g)")
  plt.ylabel("Cell Potential (V)")
  plt.legend(
    fontsize='medium',
    ncol=1,
    frameon=True, 
    edgecolor='black'
  )
  plt.ylim((2.0,4.5))
  plt.title("Voltage vs. Specific Capacity")
  plt.tight_layout()
  plt.savefig(figname)
  plt.show()
  plt.clf()
  color = next(colors)

  # Energy density plot
  plt.clf()
  energy_density_list = []
  for i, file in enumerate(pkl_files):
    file = str(file_path) + str(file)
    solution_df = pd.read_pickle(file)
    solution = solution_df.reset_index().to_numpy().T

    phi_ed_indices = np.where(solution_df.columns == "phi_ed")[0]
    phi_ptr = 1 + phi_ed_indices[-1]
  
    for j in range(int(solution[1, -1])):
      cycle = solution_df[solution_df.iloc[:, 0] == j + 1]
      t_0 = cycle.index[0]
      capacity_mAhcm2 = 0.1 * (cycle.index - t_0) * abs(cycle.iloc[:, 1]) / 3600
      capacity_mAhg = capacity_mAhcm2 / mass_loading_list[i]

      # Voltage
      voltage = cycle.iloc[:, phi_ptr - 1].to_numpy()
      capacity = capacity_mAhg.to_numpy()

      # Compute Energy Density (Wh/g)
      energy_density = np.trapezoid(voltage, capacity) / 1000
      energy_density_list.append(energy_density)
      break  # Only take first cycle for energy density

  # Plot Energy Density vs Average Particle Radius
  print('avg_radii', avg_radii, 'energy density', energy_density_list)
  plt.plot(avg_radii, energy_density_list, marker='o', linestyle='-', color='tab:blue')
  plt.xlabel("Average Particle Radius (μm)")
  plt.ylabel("Energy Density (Wh/g)")
  plt.title("Energy Density vs. Particle Radius")
  plt.grid(True)
  plt.tight_layout()
  plt.savefig(str(file_path) + 'energy_density_vs_radius.png')
  plt.show()

#========================================#
#       COMMAND LINE FUNCTIONALIY        #
#========================================#
if __name__ == '__main__':
  import argparse
  parser = argparse.ArgumentParser()
  parser.add_argument('--cores')
  parser.add_argument('--output_dir')
  parser.add_argument('--process') # plotting
  parser.add_argument('--structure') # what is being changed? anode/cathode
  parser.add_argument('--skip') # skips to process
  args = parser.parse_args()

  # Makes sure each particle has a volume fraction
  if len(param_list["r_p"]) != len(param_list["eps_solid"]):
    raise ValueError("Error: 'r_p' and 'eps_solid' must have the same number of elements!")
  if args.skip:
     print('Skipping to data processing')
  else:
    bat_can_loop(args.cores, param_list, structure=args.structure, output_dir=args.output_dir, input_file=input_file)

  # If user passes process flag, process data for each file
  if args.process:
    print(f"\n Processing data for {len(param_list["r_p"])} files")
    if args.output_dir is not None:
      file_path = str(args.output_dir) + '/'
    else:
      file_path = 'driver/'

    # Process for multiple particl model
    if input_file == 'mpm_porous_LCO.yaml' or input_file == 'LFP_MPM.yaml':
      print('param list: ',param_list)
      process_mpm_data(file_path,param_list=param_list, structure=args.structure)
              
