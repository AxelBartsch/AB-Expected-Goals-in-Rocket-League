import json
import csv
import math
import os
import carball
import numpy as np

def calculate_angle(x, y, z):
    if x != 0 and y!= 0 and z!=0:
        a = np.array([x, y, z])  # shot
        b = np.array([-895, 5120, 0])  # left post
        c = np.array([895, 5120, 0])  # right post

        ba = a - b
        bc = c - b

        cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
        angle = np.arccos(cosine_angle)

        #print(np.degrees(angle))
        return np.degrees(angle)
    else:
        return 0



def shot_type(shot_data):
    shot_type = []
    #determine how shooter came to shoot the ball, don't use elif because shot can have multiple types
    #variable will later be one-hot encoded
    if 'passed' in shot_data:
        shot_type.append('pass')
    if 'dribbleContinuation' in shot_data:
        shot_type.append('dribble')
    if 'aerial' in shot_data:
        shot_type.append('aerial')
    if len(shot_type) == 0:
        shot_type.append('open play')

    return shot_type

def which_y(data, playerId, y):
    for i in data['teams']:
        if playerId in i['playerIds'] and i['isOrange'] is True:
            y = y + 5120 #5120 is y coordinate of backwall/endline
        else:
            y = 5120 - y
    return y

def num_defenders(frame_number,raw_data,data):
    shoot = {}
    # get shot frames
    for i in data['gameStats']['hits']:
        if 'shot' in i:
            shoot.update({i['frameNumber']: [i['ballData']['posX'], i['ballData']['posY'], i['ballData']['posZ']]})

    shooters = {}
    defenders = {}
    frame_counter = 0
    # Find which car took the shot
    for frame in raw_data['network_frames']['frames']:
        frame_counter += 1
        cars = {}
        shooter = 0
        for actor in frame['updated_actors']:
            x_raw, y_raw, z_raw = 0, 0, 0
            dif = 0
            if frame_counter == frame_number:
                if 'RigidBody' in actor['attribute']:
                    # print(frame_number, shoot.get(frame_number))
                    # print(frame_number, actor['attribute']['RigidBody']['location'])
                    car = actor['attribute']['RigidBody']['location']
                    x = shoot.get(frame_counter)
                    x_raw = car['x']
                    y_raw = car['y']
                    z_raw = car['z']
                    dif = (abs(x[0]) - abs(x_raw)) + (abs(x[1]) - abs(y_raw)) + (abs(x[2]) - abs(z_raw))
                    cars.update({dif: [x_raw, y_raw, z_raw]})
                    defenders.update({dif: [x_raw, y_raw, z_raw]})
                difs = cars.keys()
                abs_difs = [abs(element) for element in difs]
                if len(abs_difs) != 0:
                    shooter = min(abs_difs)
                if cars.get(shooter) is None:
                    # print(frame_number, shooter, cars.get(-shooter))
                    shooters.update({frame_counter: [shooter, cars.get(-shooter)]})
                else:
                    # print(frame_number, shooter, cars.get(shooter))
                    shooters.update({frame_counter: [shooter, cars.get(shooter)]})

    #print("shooters: ", shooters)
    shooter_ = shooters.get(frame_number)
    if shooter_ is not None:
        sh = shooter_[0]
        # print(ex2[1])
        for key in defenders:
            if abs(key) == sh:
                defenders.pop(key)
                break
        # print("defenders: ", defenders)

        shooter_pos = shooter_[1]
        if shooter_pos is None:
            return 0
        shooter_x = shooter_pos[0]
        shooter_y = shooter_pos[1]
        num_defenders = 0

        for defender in defenders:
            def_position = defenders.get(defender)
            # if shooter_x < 0: #x = 0 is the center of the field
            if abs(shooter_y) < abs(def_position[1]) and abs(def_position[0]) < abs(shooter_x) and abs(
                    def_position[0]) > -895:  # 895 is coordinate of goal post
                num_defenders += 1
        #print("num defenders: ", num_defenders)
        if num_defenders > 3:
            return 3
        else:
            return num_defenders
    else:
        return 0


def get_pressure(frame_number, data, raw_data):
    shoot = {}
    # get shot frames
    for i in data['gameStats']['hits']:
        if 'shot' in i:
            shoot.update({i['frameNumber']: [i['ballData']['posX'], i['ballData']['posY'], i['ballData']['posZ']]})

    shooters = {}
    defenders = []
    frame_counter = 0
    # Find which car took the shot
    for frame in raw_data['network_frames']['frames']:
        frame_counter += 1
        shooter = 0
        for actor in frame['updated_actors']: #each actor is game object
            x_raw, y_raw, z_raw = 0, 0, 0
            dif = 0
            if frame_counter == frame_number:
                if 'RigidBody' in actor['attribute']: #every actor with a RigidBody is a car (ball not included in updated actors)
                    # print(frame_number, shoot.get(frame_number))
                    # print(frame_number, actor['attribute']['RigidBody']['location'])
                    car = actor['attribute']['RigidBody']['location']
                    x = shoot.get(frame_counter)
                    x_raw = car['x']
                    y_raw = car['y']
                    z_raw = car['z']
                    dif = (abs(x[0]) - abs(x_raw)) + (abs(x[1]) - abs(y_raw)) + (abs(x[2]) - abs(z_raw))
                    defenders.append(abs(dif))

    defenders.sort()
    if len(defenders) > 0:
        defenders.pop(0) #remove shooter
        for defender in defenders:
            if defender < 150:
                return 1
            else:
                return 0
    else:
        return 0

#Compile all the stats into one line that can be written to the csv
def get_stats(data, raw_data):
    shots = []
    frameNumber, playerId, goal, = 0, 0, 0
    distanceToGoal, angleToGoal = 0, 0
    x, y ,z = 0.0, 0.0, 0.0
    type_shot = []
    numb_defenders = 0
    under_pressure = 0

    for i in data['gameStats']['hits']:
        shot = []
        if 'shot' not in i:
            continue
        elif 'goal' not in i: #shot did not result in goal
            frameNumber = i['frameNumber']
            playerId = i['playerId']['id']
            distanceToGoal = i['distanceToGoal']
            goal = 0
            x = i['ballData']['posX']
            y = i['ballData']['posY']
            z = i['ballData']['posZ']
            yToGoal = which_y(data, playerId, y)
            angleToGoal = calculate_angle(abs(x), abs(yToGoal), z)
            type_shot = shot_type(i)
            numb_defenders = num_defenders(frameNumber, raw_data, data)
            under_pressure = get_pressure(frameNumber, data, raw_data)
        else: #Shot resulted in goal, everything but goal=1 is the same as above
            frameNumber = i['frameNumber']
            playerId = i['playerId']['id']
            distanceToGoal = i['distanceToGoal']
            goal = 1
            x = i['ballData']['posX']
            y = i['ballData']['posY']
            z = i['ballData']['posZ']
            yToGoal = which_y(data, playerId, y)
            angleToGoal = calculate_angle(abs(x), abs(yToGoal), z)
            type_shot = shot_type(i)
            numb_defenders = num_defenders(frameNumber, raw_data, data)
            under_pressure = get_pressure(frameNumber, data, raw_data)

        shot.append(playerId)
        shot.append(frameNumber)
        shot.append(goal)
        shot.append(distanceToGoal)
        shot.append(z)
        shot.append(angleToGoal)
        shot.append(type_shot)
        shot.append(numb_defenders)
        shot.append(under_pressure)

        shots.append(shot)
    return shots
def main():
    fields = ['ID', 'frameNumber', 'Goal', 'distanceToGoal', 'Height', 'angleToGoal', 'shotType', 'numDefenders', 'underPressure']
    csvname = "shooting_data_23.csv"
    dirname = 'replays'

    '''Funtion to write to a csv file and fill it with shooting data'''
    file_counter = 0
    with open(csvname, 'w', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(fields)
        analysis = sorted(os.listdir('rlcs_analysis_23'))
        _json = sorted(os.listdir('rlcs_json_23'))
        for filename1, filename2 in zip(analysis, _json):
            file_counter += 1
            print(file_counter)
            file1 = os.path.join('rlcs_analysis_23', filename1)
            file2 = os.path.join('rlcs_json_23', filename2)
            if os.path.isfile(file1) and os.path.isfile(file2):
                f = open(file1)
                f2 = open(file2)
                data = json.load(f)
                raw_data = json.load(f2)
                shots = get_stats(data, raw_data)
                for shot in shots:
                    csvwriter.writerow(shot)


    f.close()

    '''Function to covert replay files to analysis.json and .json files
    This function should not run simultaenously as the above function to write to the csv file
    They could (should) both be in their own separate methods
    '''
    directory = 'rlcs_season23'
    counter = 0

    for path, subfolders, filenames in os.walk(directory):
        for filename in filenames:
            file = os.path.join(path, filename)
            if os.path.isfile(file):
                counter += 1
                print('is file', counter)
                txt = str(file)
                x = txt.split(".")
                z = x[0].split("\\")
                output1 = "rlcs_analysis_23/" + z[len(z)-1] + "analysis" + ".json"
                output2 = "rlcs_json_23/" + z[len(z)-1] + ".json"
                analysis_manager = carball.analyze_replay_file(file)
                _json = analysis_manager.get_json_data()
                basic_json = carball.decompile_replay(file)

                json_object1 = json.dumps(_json, indent=2)
                with open(output1, "w") as outfile:
                    outfile.write(json_object1)
                json_object2 = json.dumps(basic_json, indent=2)
                with open(output2, "w") as outfile:
                    outfile.write(json_object2)


if __name__ == "__main__":
    main()















