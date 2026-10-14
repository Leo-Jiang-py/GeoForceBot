"""GeoForceBot entry point."""

#!/usr/bin/python3
import rospy
from geometry_msgs.msg import Twist
import time
import cv2
from ultralytics import YOLO
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
from mr_voice.msg import Voice
from std_msgs.msg import String
from RobotChassis import RobotChassis
import requests
import json
import base64
import os

def callback_Image(msg):
    global _image
    _image = CvBridge().imgmsg_to_cv2(msg, "bgr8")

def callback_Depth(msg):
    global _depth
    _depth = CvBridge().imgmsg_to_cv2(msg)

def callback_voice(msg):
    global _voice
    _voice = msg

def check_people():
    tf = False
    box = None
    if res_yolo is None: return False
    for c, (x1, y1, x2, y2) in zip(res_yolo.boxes.cls, res_yolo.boxes.xyxy):
        c, x1, y1, x2, y2 = map(int, (c, x1, y1, x2, y2))
        if model_yolo.names[c] == "person":
            tf = True
            cv2.rectangle(_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
            if box is None or (x2 - x1) * (y2 - y1) > (box[2] - box[0]) * (box[3] - box[1]):
                box = [x1, y1, x2, y2]
    return tf



def prompt_to_dict(prompt):
   return {"type": "text", "text": prompt}


def image_path_to_dict(image_path):
   if image_path is None:
       return {}
   with open(image_path, "rb") as f:
       b64 = base64.b64encode(f.read()).decode('utf-8')
   return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
def send_request(prompt, image_path="tmp.jpg"):
   response = requests.post(
       url = "http://fablabai.pcms.dpdns.org/v1/chat/completions",
       headers = {
           "Authorization": f"Bearer {os.environ['GEOFORCEBOT_API_KEY']}",
           "Content-Type": "application/json"
       },
       data = json.dumps({
           "model": "qwen/qwen3.5-9b",
           "messages": [
           {
               "role": "user",
               "content": [
                   prompt_to_dict(prompt),
                   image_path_to_dict("tmp.jpg")
               ]
           }
           ]
       })
   )
   response_msg = response.json()["choices"][0]["message"]
   print(response_msg["content"])
   return response_msg["content"].strip()


prompt = "Tell me the closest people to the screen's shirt colour, only answer one word like Black, white, etc, don't add any other word in your response"
prompt1 = "Tell me the closest people to the screen wear mask or not, only answer one word Yes or No, don't add any other word in your response"


response = [0]
response1 = [0]
def get_shirtcolour(image):
   response = send_request(prompt, "tmp.jpg")
   return response


def get_mask(image):
   response1 = send_request(prompt1, "tmp.jpg")
   mask = False
   if response1[0] == "Y":
       mask = True
   return mask



if __name__=="__main__":
    rospy.init_node("demo")
    model_yolo = YOLO("yolov8n.pt")

    _image = None
    _depth = None
    _voice = None
    res_yolo = None
    _state = 0

    g1_name = g2_name = None
    g1_drink = g2_drink = None
    g1_gender = g2_gender = None
    g1_glasses = g2_glasses = None

    robot = RobotChassis()
    pub_cmd = rospy.Publisher("/cmd_vel", Twist, queue_size=10)
    pub_say = rospy.Publisher("/speaker/say", String, queue_size=10)

    rospy.Subscriber("/camera/rgb/image_raw", Image, callback_Image)
    rospy.Subscriber("/camera/depth/image_raw", Image, callback_Depth)
    rospy.Subscriber("/voice/text", Voice, callback_voice)

    rospy.sleep(1)
    rate = rospy.Rate(20)
    print("hello")
    pub_say.publish("Hello")
    rospy.sleep(2)
    while not rospy.is_shutdown():
        rate.sleep()
        if _image is None or _depth is None:
            continue

        res_yolo = model_yolo(_image, verbose=False)[0]

        # --- State Machine ---
        # GUEST 1 SECTION
        if _state == 0:
            if check_people():
                _state = 1

        elif _state == 1:
            pub_say.publish("welcome, What's your name?")
            rospy.sleep(2)
            _state = 2

        elif _state == 2:
            if _voice is not None:
                names = ["adam", "exo", "chris", "hunter", "jack", "paris", "william", "robin", "olivia", "max"]
                text_lower = _voice.text.lower()
                for name in names:
                    if name in text_lower:
                        g1_name = name
                        pub_say.publish("welcome " + str(g1_name))
                        _state = 3
                        break
                _voice = None

        elif _state == 3:
            pub_say.publish("And now, What do you want to drink?")
            rospy.sleep(1)
            _state = 4

        elif _state == 4:
            if _voice is not None:
                drinks = ["orange", "coke", "coffee", "cocoa", "milk", "lemonade", "soda", "green", "black", "wine"]
                text_lower = _voice.text.lower()
                for drink in drinks:
                    if drink in text_lower:
                        g1_drink = drink
                        if drink == "green" or drink == "black":
                            g1_drink = str(drink) + " tea"
                        if drink == "orange":
                            g1_drink = str(drink) + " juice"
                        if drink == "milk":
                            g1_drink = "coconut milk"
                        pub_say.publish("ok, you would like to drink " + str(g1_drink))
                        _state = 5
                        break
                _voice = None

        elif _state == 5:
            pub_say.publish("Are you a boy or girl, what is your gender?")
            rospy.sleep(1)
            _state = 6

        elif _state == 6:
            if _voice is not None:
                genders = ["boy", "girl"]
                text_lower = _voice.text.lower()
                for gender in genders:
                    if gender in text_lower:
                        g1_gender = gender
                        pub_say.publish("ok, you are a " + str(g1_gender))
                        _state = 7
                        break
                _voice = None

        elif _state == 7:
            pub_say.publish("Are you wearing glasses, yes or no?")
            rospy.sleep(1)
            _state = 8

        elif _state == 8:
            if _voice is not None:
                if "yes" in _voice.text.lower():
                    g1_glasses = "yes"
                    _state = 9
                elif "no" in _voice.text.lower():
                    g1_glasses = "no"
                    _state = 9
                _voice = None
            cv2.imwrite("tmp.jpg", _image)
            _colour = get_shirtcolour(_image)
            _mask = get_mask(_image)
        elif _state == 9:
            pub_say.publish("Please follow me to my master")
            rospy.sleep(3)
            _state = 15


        elif _state == 12:
            pub_say.publish("this is " + str(g1_name))
            pub_say.publish("a " + str(g1_gender))
            pub_say.publish("he wants to drink " + str(g1_drink))
            _state = pre_state


        elif _state == 15:
            robot.move_to(-2.01, -1.51, 0.0)
            _state = 16

        elif _state == 16:
            if robot.status_code == 3:
                _state = 17
            else:
                _state -= 1

        elif _state == 17:
            robot.move_to(0.378, -0.435, 0.0)
            _state = 18

        elif _state == 18:
            if robot.status_code == 3:
                _state = 19
            else:
                _state -= 1

        elif _state == 19:
            robot.move_to(0, 0, 1.57)
            _state = 19.01
        elif _state == 19.01:
            if robot.status_code == 3:
                _state = 19.02
            else:
                _state = 19
        elif _state == 19.02:
            if check_people():
                pre_state = 19.1
                _state = 12
            else:
                pre_state = 0
                _state = 19.1
                empty_seat = 'a'

            print("48")
        elif _state == 19.1:
            robot.move_to(0, 0, 1.57*3/2)
            _state = 19.11
        elif _state == 19.11:
            if robot.status_code == 3:
                _state = 19.12
            else:
                _state = 19.1
        elif _state == 19.12:
            if check_people():
                if not pre_state == 19.1:
                    _state = 12
                else:
                    robot.move_to(0, 0, 1.57/2)
                    empty_seat = 'c'
                    _state = 20
            else:
                robot.move_to(0, 0, 1.57/2)
                empty_seat = 'b'
                _state = 20

        elif _state == 20:
            if empty_seat == 'a':
                robot.move_to(0, 0, 1.57)
            elif empty_seat == 'b':
                robot.move_to(0, 0, 1.57*3/2)
            else:
                robot.move_to(0, 0, 1.57/2)
            _state = 21
        elif _state == 21:
            if robot.status_code == 3:
                _state = 21.1
            else:
                _state = 20
        elif _state == 21.1:
            pub_say.publish("this is your seat")
            _state = 22


        elif _state == 22:
            robot.move_to(0.378, -0.435, 0.0)
            _state = 23

        elif _state == 23:
            if robot.status_code == 3:
                _state = 24
            else:
                _state -= 1

        elif _state == 24:
            robot.move_to(-2.01, -1.51, 0.0)
            _state = 25

        elif _state == 25:
            if robot.status_code == 3:
                _state = 26
            else:
                _state -= 1

        elif _state == 26:
            robot.move_to(-1.73, 1.69, -1.57)
            _state = 27

        elif _state == 27:
            if robot.status_code == 3:
                _state = 28
            else:
                _state -= 1

        # GUEST 2 SECTION
        elif _state == 28:
            if check_people():
                _state = 29

        elif _state == 29:
            pub_say.publish("Hello, What's your name?")
            rospy.sleep(2)
            _state = 30

        elif _state == 30:
            if _voice is not None:
                text_lower = _voice.text.lower()
                for name in names:
                    if name in text_lower:
                        g2_name = name
                        pub_say.publish("he is " + str(g2_name))
                        _state = 31
                        break
                _voice = None

        elif _state == 31:
            pub_say.publish("And now, What do you want to drink?")
            rospy.sleep(1)
            _state = 32

        elif _state == 32:
            if _voice is not None:
                text_lower = _voice.text.lower()
                for drink in drinks:
                    if drink in text_lower:
                        g2_drink = drink
                        if drink == "green" or drink == "black":
                            g2_drink = str(drink) + " tea"
                        if drink == "orange":
                            g2_drink = str(drink) + " juice"
                        if drink == "milk":
                            g2_drink = "coconut milk"
                        pub_say.publish("he would like to drink " + str(g2_drink))
                        _state = 43
                        break
                _voice = None

        elif _state == 33:
            if check_people():
                pub_say.publish("he is a" + str(g1_gender))
                pub_say.publish("he is wearing a")
                pub_say.publish(str(_colour))
                pub_say.publish("shirt")
                if _mask == True:
                    pub_say.publish("he is wearing mask")
                else:
                    pub_say.publish("he is not wearing mask")

                if g1_glasses == "yes":
                    pub_say.publish("guest 1 is wearing glasses")
                else:
                    pub_say.publish("guest 1 is not wearing glasses")
                rospy.sleep(3)
                pub_say.publish("please follow me to your seat")
                _state = 43

        elif _state == 40:
            pub_say.publish("this is " + str(g2_name))
            pub_say.publish("a " + str(g2_gender))
            pub_say.publish("and he would like to drink " + str(g2_drink))
            _state = pre_state

        elif _state == 43:
            robot.move_to(-2.01, -1.51, 0.0)
            _state = 44

        elif _state == 44:
            if robot.status_code == 3:
                _state = 45
            else:
                _state -= 1
            print("45")

        elif _state == 45:
            robot.move_to(0.378, -0.435, 0.0)
            _state = 46
            print("46")
        elif _state == 46:
            if robot.status_code == 3:
                _state = 47
            else:
                _state -= 1
            print("47")
        elif _state == 47:
            robot.move_to(0, 0, 1.57)
            _state = 47.01
        elif _state == 47.01:
            if robot.status_code == 3:
                _state = 47.02
            else:
                _state = 47
        elif _state == 47.02:
            if check_people():
                pre_state = 47.1
                _state = 40
            else:
                pre_state = 0
                empty_seat = 'a'
                _state = 47.1

            print("48")
        elif _state == 47.1:
            robot.move_to(0, 0, 1.57*3/2)
            _state = 47.11
        elif _state == 47.11:
            if robot.status_code == 3:
                _state = 47.12
            else:
                _state = 47.1
        elif _state == 47.12:
            if check_people():
                if not pre_state == 47.1:
                    _state = 40
                else:
                    robot.move_to(0, 0, 1.57/2)
                    empty_seat = 'c'
                    _state = 48
            else:
                robot.move_to(0, 0, 1.57/2)
                empty_seat = 'b'
                _state = 48


        elif _state == 48:
            if empty_seat == 'a':
                robot.move_to(0, 0, 1.57)
            elif empty_seat == 'b':
                robot.move_to(0, 0, 1.57*3/2)
            else:
                robot.move_to(0, 0, 1.57/2)
            _state = 49
        elif _state == 49:
            if robot.status_code == 3:
                _state = 49.1
            else:
                _state = 48
        elif _state == 49.1:
            pub_say.publish("this is your seat")
            _state = 33
            print("50")
        elif _state == 50:
            robot.move_to(0.378, -0.435, 0.0)
            _state = 51
            print("51")
        elif _state == 51:
            if robot.status_code == 3:
                _state = 52
            else:
                _state -= 1
            print("52")
        elif _state == 52:
            robot.move_to(-2.01, -1.51, 0.0)
            _state = 53
            print("53")
        elif _state == 53:
            if robot.status_code == 3:
                _state = 54
            else:
                _state -= 1
            print("54")
        elif _state == 54:
            robot.move_to(-1.73, 1.69, -1.57)
            _state = 55
            print("55")
        elif _state == 55:
            if robot.status_code == 3:
                _state = 56
            else:
                _state -= 1

        elif _state == 56:
            pub_say.publish("finish")
            _state = 57 # Task complete


        cv2.imshow("_image", _image)
        cv2.imshow("_depth", _depth)
        if cv2.waitKey(1) in (27, ord('q')):
            break
