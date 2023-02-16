#!/usr/bin/env python

# Copyright (c) 2019 Computer Vision Center (CVC) at the Universitat Autonoma de
# Barcelona (UAB).
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.
import os
os.environ['CUDA_LAUNCH_BLOCKING'] = '1'

import glob
import os
import sys
import numpy as np
import matplotlib.pyplot as plt
import cv2
import torch
try:
    sys.path.append(glob.glob('../carla/dist/carla-*%d.%d-%s.egg' % (
        sys.version_info.major,
        sys.version_info.minor,
        'win-amd64' if os.name == 'nt' else 'linux-x86_64'))[0])
except IndexError:
    pass

import carla
import pdb
from carla import Transform, Location, Rotation

import random
import time
import pdb

# import for model
from models.my_models import MyModel1
# import for visualization
import io
import matplotlib.pyplot as plt 
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches

IMG_SIZE = [800,560]
CAR_WIDTH = 2.0
CAR_LENGTH = 3.7
FIG_SIZE = [8,8] 
MODEL_PATH = './models/mynet_4.pth'
    
def norm_vector(vector=carla.Vector3D):
    length = (vector.x**2 + vector.y**2 + vector.z**2)**(1/2)
    return length        
        

def visualize_image(image, plt):
    data = np.array(image.raw_data) # shape is (image.height * image.width * 4,) 
    data_reshaped = np.reshape(data, (image.height, image.width,4))
    rgb_3channels = data_reshaped[:,:,:3] # first 3 channels 
    flipped = cv2.flip(rgb_3channels, 1)
    image_sum = np.concatenate((plt, flipped), axis = 1) 
    cv2.imshow("plot location and camera view",image_sum)
    cv2.waitKey(10)
    
    
def car_patch_pos(x, y, psi, car_width = 1.0):
    # Shift xy, centered on rear of car to rear left corner of car. 
    x_new = x - np.sin(psi)*(car_width/2)
    y_new = y + np.cos(psi)*(car_width/2)
    return [x_new, y_new]

def update_plot(num, p_fol, p_fol_fol, p_goal, car_lead, car_follow, car_follow_follow, text_list, frame): 
    # the first ego vehicle
    plt.plot(car_follow.get_location().x,car_follow.get_location().y, 'b', marker=".", markersize=1)
    p_fol.set_xy(car_patch_pos(car_follow.get_location().x,car_follow.get_location().y, 
                               car_follow.get_transform().rotation.yaw))
    psi_follow = car_follow.get_transform().rotation.yaw
    if psi_follow < 0:
        psi_follow += 360   
    p_fol.angle = psi_follow - 90 
    
    # the second ego vehicle
    # the first ego vehicle
    plt.plot(car_follow_follow.get_location().x,car_follow_follow.get_location().y, 'g', marker=".", markersize=1)
    p_fol_fol.set_xy(car_patch_pos(car_follow_follow.get_location().x,car_follow_follow.get_location().y, 
                               car_follow_follow.get_transform().rotation.yaw))
    psi_follow_follow = car_follow_follow.get_transform().rotation.yaw
    if psi_follow_follow < 0:
        psi_follow_follow += 360   
    p_fol_fol.angle = psi_follow - 90 

    # vehicle_lead
    plt.plot(car_lead.get_location().x,car_lead.get_location().y, 'r', marker=".", markersize=1)
    p_goal.set_xy(car_patch_pos(car_lead.get_location().x,car_lead.get_location().y, car_lead.get_transform().rotation.yaw))
    psi_lead = car_lead.get_transform().rotation.yaw 
    if psi_lead < 0:
        psi_lead += 360 
    p_goal.angle = psi_lead - 90  
    text_list[0].set_text("frame : {}".format(frame))
    text_list[1].set_text('velocity of the target vehicle: % .2f m/s' % norm_vector(car_lead.get_velocity()))
    text_list[2].set_text('velocity of the first ego vehicle: % .2f m/s' % norm_vector(car_follow.get_velocity()))
    car_dis = ((car_lead.get_location().x-car_follow.get_location().x) **2 + 
               (car_lead.get_location().y-car_follow.get_location().y) **2)**0.5
    text_list[3].set_text('car distance (1.st ego vehicle): % .2f m' % car_dis)
    text_list[4].set_text('dis/v_ref (1.st ego vehicle):% .2f ' % (car_dis/(norm_vector(car_lead.get_velocity())+0.01)))
    text_list[5].set_text('velocity of the first ego vehicle: % .2f m/s' % norm_vector(car_follow.get_velocity()))
    text_list[6].set_text('velocity of the second ego vehicle: % .2f m/s' % norm_vector(car_follow_follow.get_velocity()))
    car_dis_fol = ((car_follow.get_location().x-car_follow_follow.get_location().x) **2 + 
               (car_follow.get_location().y-car_follow_follow.get_location().y) **2)**0.5
    text_list[7].set_text('car distance (2.nd ego vehicle): % .2f m' % car_dis_fol)
    text_list[8].set_text('dis/v_ref (2.nd ego vehicle):% .2f ' % (car_dis_fol/(norm_vector(car_follow.get_velocity())+0.01)))
    
def get_img_from_fig(fig, dpi=180):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=180)
    buf.seek(0)
    img_arr = np.frombuffer(buf.getvalue(), dtype=np.uint8)
    buf.close()
    img = cv2.imdecode(img_arr, 1)
    img = cv2.resize(img,(IMG_SIZE[0], IMG_SIZE[1])) 
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB) 
    return img
    

def main():
    actor_list = [] 
    try: 
        client = carla.Client('localhost', 2000)
        client.set_timeout(20.0)
        # pdb.set_trace()
        
        world = client.load_world("/Game/Carla/Maps/Town04") 
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.1
        world.apply_settings(settings)
        blueprint_library = world.get_blueprint_library()
        #bp = random.choice(blueprint_library.filter('vehicle'))
        bp1 = blueprint_library.filter('vehicle')[0]
        bp2 = blueprint_library.filter('vehicle')[0]
        bp3 = blueprint_library.filter('vehicle')[0]
        color1 = bp1.get_attribute('color').recommended_values[0]
        color2 = bp2.get_attribute('color').recommended_values[1]
        color3 = bp2.get_attribute('color').recommended_values[1]
        bp2.set_attribute('color', color2)
        bp3.set_attribute('color', color3)
   
        # Always fix the starting position 
        transform1 = world.get_map().get_spawn_points()[13]  
        vehicle_lead = world.spawn_actor(bp1, transform1)
        
        transform2 = transform1
        transform2.location.x -= 8   
        vehicle_follow = world.spawn_actor(bp2, transform2) 
        
        transform3 = transform2
        transform3.location.x -= 8   
        vehicle_follow_follow = world.spawn_actor(bp3, transform3) 
        # pdb.set_trace()

        # So let's tell the world to spawn the vehicle.  
        actor_list.append(vehicle_lead)
        actor_list.append(vehicle_follow)
        actor_list.append(vehicle_follow_follow)
        print('created target vehicle %s' % vehicle_lead.type_id)
        print('created the first ego vehicle %s' % vehicle_follow.type_id)
        print('created the second ego vehicle %s' % vehicle_follow.type_id)
        
        physics_vehicle = vehicle_follow.get_physics_control()
        car_mass = physics_vehicle.mass
        
        # Let's put the vehicle to drive around. 
        vehicle_lead.set_autopilot(True) 
         
        frame = 0
        rgb_list = list()
        
        # Let's add now an "RGB" camera attached to the vehicle.
        camera_bp_rgb = blueprint_library.find('sensor.camera.rgb')
        camera_bp_rgb.set_attribute('image_size_x',  str(IMG_SIZE[0]))
        camera_bp_rgb.set_attribute('image_size_y',  str(IMG_SIZE[1]))
        camera_bp_rgb.set_attribute('fov',  str(100))
        camera_transform_rgb = carla.Transform(carla.Location(x=-7.0, z=2.4))
        camera_rgb = world.spawn_actor(camera_bp_rgb, camera_transform_rgb, attach_to=vehicle_follow_follow)
        actor_list.append(camera_rgb)
        print('created %s' % camera_rgb.type_id)
        camera_rgb.listen(lambda image: rgb_list.append(image) if frame > 5 else None)
         
        
        #### for the first ego vehicle####
        state_i = np.array([[231.025146484375,-385.14300537109375, -2.9595362983108866, 0]])
        ref_i = np.array([[223.025146484375,-385.14300537109375,-3.1340854687929687,0]]) 
        u_i = np.array([[0,0]])   
        
        #### for the second ego vehicle####
        state_sec_i = np.array([[239.025146484375,-385.14300537109375, -2.9595362983108866, 0]])
        ref_sec_i = np.array([[231.025146484375,-385.14300537109375,-3.1340854687929687,0]]) 
        u_sec_i = np.array([[0,0]])   
        
         ##### SIMULATOR DISPLAY ######### 

        # Total Figure
        fig = plt.figure(figsize=(FIG_SIZE[0], FIG_SIZE[1]))
        gs = gridspec.GridSpec(8,8)

        # Elevator plot settings.
        ax = fig.add_subplot(gs[:8, :8]) 
        '''
        plt.xlim(-170, 300)
        ax.set_ylim([-410, -50])
        plt.xticks(np.arange(-170, 301, step=30))
        plt.yticks(np.arange(-410, -49, step=10))
        plt.title('MPC 2D')
        '''
        plt.xlim(200, 500)
        ax.set_ylim([-400, 100])
        plt.xticks(np.arange(200, 501, step=10))
        plt.yticks(np.arange(-400, 101, step=10))
        plt.title('MPC 2D')
        ## Main plot info. 
        patch_fol = mpatches.Rectangle((0, 0), CAR_WIDTH, CAR_LENGTH, fc='k', fill=True)
        patch_fol_fol = mpatches.Rectangle((0, 0), CAR_WIDTH, CAR_LENGTH, fc='k', fill=True)
        patch_goal = mpatches.Rectangle((0, 0), CAR_WIDTH, CAR_LENGTH, fc='k', ls='dashdot', fill=True)

        ax.add_patch(patch_fol)
        ax.add_patch(patch_fol_fol)
        ax.add_patch(patch_goal)
        predict, = ax.plot([], [], 'r--', linewidth = 1) 
        print('Create vehicle_follow and vehicle_lead in the figure.')
        
        # plot text
        '''
        text_pt = plt.text(-140, -60, '', fontsize=8)
        text_vlead = plt.text(-140, -70, '', fontsize=8)
        text_vfol_1 = plt.text(-140, -80, '', fontsize=8)
        text_dis = plt.text(-140, -90, '', fontsize = 8)
        text_ratio = plt.text(-140, -100, '', fontsize=8) 
        text_vfol_2 = plt.text(100, -70, '', fontsize=8)
        text_vfol_fol = plt.text(100, -80, '', fontsize=8)
        text_dis_fol = plt.text(100, -90, '', fontsize = 8)
        text_ratio_fol = plt.text(100, -100, '', fontsize=8) 
        '''
        text_pt = plt.text(230, 90, '', fontsize=8)
        text_vlead = plt.text(230, 80, '', fontsize=8)
        text_vfol_1 = plt.text(230, 70, '', fontsize=8)
        text_dis = plt.text(230, 60, '', fontsize = 8)
        text_ratio = plt.text(230, 50, '', fontsize=8) 
        text_vfol_2 = plt.text(370, 80, '', fontsize=8)
        text_vfol_fol = plt.text(370, 70, '', fontsize=8)
        text_dis_fol = plt.text(370, 60, '', fontsize = 8)
        text_ratio_fol = plt.text(370, 50, '', fontsize=8) 
        text_list = [text_pt, text_vlead, text_vfol_1, text_dis, text_ratio, text_vfol_2, text_vfol_fol, text_dis_fol, text_ratio_fol]
         
        control_values = []
        control_values_sec = []
        mynet = MyModel1(neurons = [256, 1024, 2048, 1024, 256])
        #mynet = MyModel2(neurons = [256, 512, 1024, 256])
        mynet.load_state_dict(torch.load(MODEL_PATH, map_location='cpu'))
        
        for frame in range(800):
            print('frame %s' % frame)
            # Do tick
            world.tick()
            vehicle_lead.set_autopilot(True) 
            # Always have the traffic light on green
            if vehicle_lead.is_at_traffic_light():
                traffic_light = vehicle_lead.get_traffic_light()
                if traffic_light.get_state() == carla.TrafficLightState.Red:
                        traffic_light.set_state(carla.TrafficLightState.Green)
            
            '''
            #### test by adding random impulses
            if (frame % 40) == 0 and frame != 0:          
                impulse = random.uniform(4.0,8.0) *car_mass
                minus_list = [-1,1]
                impulse_minus = random.choice(minus_list)
                impulse = impulse_minus *impulse
                impulse_axis = random.randint(0,1)
                if impulse_axis == 0:
                    vehicle_follow.add_impulse(carla.Vector3D(impulse, 0, 0))
                elif impulse_axis == 1:
                    vehicle_follow.add_impulse(carla.Vector3D(0, impulse, 0))                
                print('impulse:{}, axis:{}'.format(impulse,impulse_axis))
            '''     
            print('TARGET Vehicle')
            print("Location: (x,y,z): ({},{},{})".format(vehicle_lead.get_location().x,vehicle_lead.get_location().y, vehicle_lead.get_location().z))
            print("Throttle: {}, Steering Angle: {}, Brake: {}".format(vehicle_lead.get_control().throttle, vehicle_lead.get_control().steer, vehicle_lead.get_control().brake))
            print('THE FIRST EGO Vehicle')
            print("Location: (x,y,z): ({},{},{})".format(vehicle_follow.get_location().x,vehicle_follow.get_location().y, vehicle_follow.get_location().z))
            print("Throttle: {}, Steering Angle: {}, Brake: {}".format(vehicle_follow.get_control().throttle, vehicle_follow.get_control().steer, vehicle_follow.get_control().brake))            
            print('THE SECOND EGO Vehicle')
            print("Location: (x,y,z): ({},{},{})".format(vehicle_follow_follow.get_location().x,vehicle_follow_follow.get_location().y, vehicle_follow_follow.get_location().z))
            print("Throttle: {}, Steering Angle: {}, Brake: {}".format(vehicle_follow_follow.get_control().throttle, vehicle_follow_follow.get_control().steer, vehicle_follow_follow.get_control().brake))
             
            #### the target vehicle
            v_lead_vec = np.array([vehicle_lead.get_velocity().x, vehicle_lead.get_velocity().y,
                                    vehicle_lead.get_velocity().z])
            v_t_lead = np.linalg.norm(v_lead_vec)
            psi_t_lead = vehicle_lead.get_transform().rotation.yaw * np.pi / 180
            new_ref_lead = [vehicle_lead.get_location().x, vehicle_lead.get_location().y, psi_t_lead, v_t_lead] 
            
            #### the first ego vehicle
            v_fol_vec = np.array([vehicle_follow.get_velocity().x, vehicle_follow.get_velocity().y,
                                  vehicle_follow.get_velocity().z])
            v_t_fol = np.linalg.norm(v_fol_vec)
            psi_t_fol = vehicle_follow.get_transform().rotation.yaw * np.pi / 180
            new_ref_fol = [vehicle_follow.get_location().x, vehicle_follow.get_location().y, psi_t_fol, v_t_fol] 
            
            #### the second ego vehicle
            v_fol_fol_vec = np.array([vehicle_follow_follow.get_velocity().x, vehicle_follow_follow.get_velocity().y,
                                  vehicle_follow_follow.get_velocity().z])
            v_t_fol_fol = np.linalg.norm(v_fol_fol_vec)
            psi_t_fol_fol = vehicle_follow_follow.get_transform().rotation.yaw * np.pi / 180
            new_ref_fol_fol = [vehicle_follow_follow.get_location().x, vehicle_follow_follow.get_location().y, psi_t_fol_fol, v_t_fol_fol]
            
            if frame == 0:
                ref_i = np.expand_dims(np.array(new_ref_lead), axis=0)
                state_i = np.expand_dims(np.array(new_ref_fol), axis=0)
                ref_sec_i = np.expand_dims(np.array(new_ref_fol), axis=0)
                state_sec_i = np.expand_dims(np.array(new_ref_fol_fol), axis=0)
            else:
                ref_i = np.append(ref_i, np.array([new_ref_lead]), axis = 0)
                state_i = np.append(state_i, np.array([new_ref_fol]), axis = 0) 
                ref_sec_i = np.append(ref_i, np.array([new_ref_fol]), axis = 0)
                state_sec_i = np.append(state_i, np.array([new_ref_fol_fol]), axis = 0) 
            
            #### control value of the first ego vehicle
            '''
            det_state = state_i[-1] - ref_i[-1] 
            model_input = np.zeros((1,5))
            model_input[:,:3] = det_state[:3]
            model_input[:,3] = ref_i[-1][3]
            model_input[:,4] = state_i[-1][3]
            '''
            det_state = ref_i[-1] - state_i[-1] 
            model_input = np.zeros((1,6))
            model_input[:,:2] = det_state[:2]
            model_input[:,2] = ref_i[-1][2]
            model_input[:,3] = state_i[-1][2] 
            model_input[:,4] = ref_i[-1][3]
            model_input[:,5] = state_i[-1][3] 
            mynet.eval()
            print('input for the first ego vehicle:', model_input)
            output_pred = mynet(torch.tensor(model_input).to(torch.float32)) 
            throttle, str_angle = output_pred[0].detach().numpy()
            throttle = float(throttle) 
            str_angle = float(str_angle)
            control_values.append([throttle, str_angle])   
            u_i = np.append(u_i, np.array([(throttle, str_angle)]), axis=0)  
            vehicle_follow.apply_control(carla.VehicleControl(throttle=throttle, steer=str_angle))
            
            #### control value of the second ego vehicle
            '''
            det_state_sec = state_sec_i[-1] - ref_sec_i[-1] 
            model_input_sec = np.zeros((1,5))
            model_input_sec[:,:3] = det_state_sec[:3]
            model_input_sec[:,3] = ref_sec_i[-1][3]
            model_input_sec[:,4] = state_sec_i[-1][3]
            '''
            det_state_sec = ref_sec_i[-1] - state_sec_i[-1] 
            model_input_sec = np.zeros((1,6))
            model_input_sec[:,:2] = det_state_sec[:2]
            model_input_sec[:,2] = ref_sec_i[-1][2]
            model_input_sec[:,3] = state_sec_i[-1][2] 
            model_input_sec[:,4] = ref_sec_i[-1][3]
            model_input_sec[:,5] = state_sec_i[-1][3] 
            mynet.eval()
            print('input for the second ego vehicle:', model_input_sec)
            output_pred_sec = mynet(torch.tensor(model_input_sec).to(torch.float32)) 
            throttle_sec, str_angle_sec = output_pred_sec[0].detach().numpy()
            throttle_sec = float(throttle_sec) 
            str_angle_sec = float(str_angle_sec)
            control_values_sec.append([throttle_sec, str_angle_sec])   
            u_sec_i = np.append(u_sec_i, np.array([(throttle_sec, str_angle_sec)]), axis=0)  
            vehicle_follow_follow.apply_control(carla.VehicleControl(throttle=throttle_sec, steer=str_angle_sec))
            
            ###### Visualization ######
            update_plot(frame, patch_fol, patch_fol_fol, patch_goal, vehicle_lead, vehicle_follow, vehicle_follow_follow, text_list, frame) 
            fig.canvas.draw()  
            img_loc = get_img_from_fig(fig, dpi=180) 
            if frame > 11:
                visualize_image(rgb_list[-1], img_loc)   
    
    finally:

        print('destroying actors')
        camera_rgb.destroy()
        client.apply_batch([carla.command.DestroyActor(x) for x in actor_list])
        print('done.')


if __name__ == '__main__':

    main()
