import time
 
import cv2
from vision import ScreenCapture,TemplateMatch
from TableList import TableListHandler

from InterceptionCommunication import InterceptionInput
# wireshard ip.addr == 84.44.82.2 && tcp.flags.push == 1 && tcp.len > 1000

interception_input = InterceptionInput()
screen_capture = ScreenCapture()
table_handler = TableListHandler()
 # x,y= 843,467  > 463x255
 # offset+264+148
time.sleep(1)
def run_loop():
    executed_once = True
    while True:
        time.sleep(0.02)
        screen_capture.update()
        result = screen_capture.find_template("table_left_corner", threshold=0.7)
        if type(result) == TemplateMatch:
            
            if executed_once:
                lowtohigh_result = screen_capture.find_template("lowtohigh", threshold=0.7)
                if type(lowtohigh_result) == TemplateMatch:
                     interception_input.move(lowtohigh_result.center[0], lowtohigh_result.center[1])
                    #  interception_input.click("left")
                     executed_once = False
            else:  
                     
                print(f"Template found at {result.bbox} with confidence {result.confidence}")
                region_img = result.region_img
                region_img = table_handler.process_img(region_img)
                
                next_result = screen_capture.find_template("next", threshold=0.7)
                break
                if type(next_result) == TemplateMatch:
                    interception_input.move(next_result.center[0], next_result.center[1])
                    interception_input.click("left")
                    
                else:
                    print("Next template not found")
                    break
 
        else:
            print("Template not found",result)
        
        time.sleep(0.01)   
        
        

if __name__ == "__main__":
    # Örnek: 20 FPS hedefiyle çalıştır
    run_loop()