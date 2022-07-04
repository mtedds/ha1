import Database
# TODO: Add controller database as a variable (changing it means editing it in 4-5 places!)
import Message
import time
import subprocess
# TODO: Remove this for Production
import importlib
importlib.reload(Database)
importlib.reload(Message)

import logging


if request.application not in logging.root.manager.loggerDict:
    logger = logging.getLogger(request.application)
    logger.setLevel(logging.DEBUG)
    f_handler = logging.FileHandler("/var/log/web2py/web2py.log")
    f_handler.setLevel(logging.DEBUG)
    f_format = logging.Formatter("%(asctime)s:%(levelname)s: %(message)s")
    f_handler.setFormatter(f_format)
    logger.addHandler(f_handler)
else:
    logger = logging.getLogger(request.application)


def index():
    my_database = Database.Database("/home/pi/controller/controller/controller.db", logger)
    # response.flash = T("Hello World")
    sensors = my_database.read_all_sensors()

    controllerProcess = subprocess.run(['systemctl', 'is-active',  'controller'],
                             stdout=subprocess.PIPE,
                             universal_newlines=True)
    controllerProcess

    ISGProcess = subprocess.run(['applications/ha1/modules/checkisg.sh'],
                                       stdout=subprocess.PIPE,
                                       universal_newlines=True)
    ISGProcess

    MyCProcess = subprocess.run(['applications/ha1/modules/checkmyc.sh'],
                                       stdout=subprocess.PIPE,
                                       universal_newlines=True)
    MyCProcess

    # These are not really sensors!
    sensors["HC is on"] = my_database.hp_is_on("HC")
    sensors["DHW is on"] = my_database.hp_is_on("DHW")
    sensors["HC next switch"] = my_database.next_relay_switch_time("HC")[0:5]
    sensors["DHW next switch"] = my_database.next_relay_switch_time("DHW")[0:5]
    sensors["Radiators next switch"] = my_database.next_relay_switch_time("Radiators relay")[0:5]
    sensors["Ufloor ground next switch"] = my_database.next_relay_switch_time("Ufloor ground relay")[0:5]
    sensors["Ufloor first next switch"] = my_database.next_relay_switch_time("Ufloor first relay")[0:5]
    sensors["Controller status"] = controllerProcess.stdout
    sensors["ISG status"] = ISGProcess.stdout
    sensors["MyController status"] = MyCProcess.stdout

    return dict(message=sensors)


def indexB():
    return index()


def prog():
    logger.debug(f"prog {request.vars}")
    my_database = Database.Database("/home/pi/controller/controller/controller.db", logger)
    return dict(message=my_database.read_prog(request.vars["sensor"]))

def progB():
    logger.debug(f"progB {request.vars}")
    return prog()


def allprog():
    logger.debug(f"allprog {request.vars}")
    my_database = Database.Database("/home/pi/controller/controller/controller.db", logger)
    all_progs = {}
    titles = {"DHW" : "Hot water"
            , "HC": "Heating"
            , "Radiators relay": "Radiators"
            , "Ufloor ground relay": "Ufloor ground"
            , "Ufloor first relay": "Ufloor first"
              }
    for sensor in titles.keys():
        all_progs[titles[sensor]] = my_database.read_prog(sensor)
    return dict(message=all_progs)


def setsensor():
    # Parameters: sensor value [time]
    logger.debug(f"setsensor {request.vars}")
    my_message = Message.Message("homeserver", 1883, 60, "web2py", when_message, {}, logger)
    my_database = Database.Database("/home/pi/controller/controller/controller.db", logger)

    send_value = request.vars["value"]

    # If time added, then this will need to be triggered so add to message
    if "time" in request.vars.keys():
        send_value = f"{send_value},{request.vars['time']}"

    # TODO If this is just a "normal" set sensor (with no intervals - eg. Comfort temp) then do not try to return the next switch time
    my_message.set_sensor_control(request.vars["sensor"], send_value)
    time.sleep(1)
    nextRelay = my_database.next_relay_switch_time_value(request.vars["sensor"], request.vars["value"])
    if len(nextRelay) == 0:
        return dict(message="Ok")
    return dict(message=my_database.next_relay_switch_time_value(request.vars["sensor"], request.vars["value"])[0:5])


def settrigger():
    # Parameters: sensor day group 0/1 time
    logger.debug(f"settrigger {request.vars}")
    my_message = Message.Message("homeserver", 1883, 60, "web2py", when_message, {}, logger)

    return my_message.set_trigger_control(request.vars["sensor"], request.vars["day"], request.vars["group"],
                                          request.vars["value"], request.vars["time"])


def when_message(client, userdata, msg):
    # This is a dummy method just for the Message object above
    pass


def test():
    my_database = Database.Database("/home/pi/controller/controller/controller.db", logger)
    # response.flash = T("Hello World")
    sensors = my_database.read_all_sensors()
    return dict(message=sensors)

def test2():
    return test()

# ---- API (example) -----
@auth.requires_login()
def api_get_user_email():
    if not request.env.request_method == 'GET': raise HTTP(403)
    return response.json({'status':'success', 'email':auth.user.email})

# ---- Smart Grid (example) -----
@auth.requires_membership('admin') # can only be accessed by members of admin groupd
def grid():
    response.view = 'generic.html' # use a generic view
    tablename = request.args(0)
    if not tablename in db.tables: raise HTTP(403)
    grid = SQLFORM.smartgrid(db[tablename], args=[tablename], deletable=False, editable=False)
    return dict(grid=grid)

# ---- Embedded wiki (example) ----
def wiki():
    auth.wikimenu() # add the wiki to the menu
    return auth.wiki() 

# ---- Action for login/register/etc (required for auth) -----
def user():
    """
    exposes:
    http://..../[app]/default/user/login
    http://..../[app]/default/user/logout
    http://..../[app]/default/user/register
    http://..../[app]/default/user/profile
    http://..../[app]/default/user/retrieve_password
    http://..../[app]/default/user/change_password
    http://..../[app]/default/user/bulk_register
    use @auth.requires_login()
        @auth.requires_membership('group name')
        @auth.requires_permission('read','table name',record_id)
    to decorate functions that need access control
    also notice there is http://..../[app]/appadmin/manage/auth to allow administrator to manage users
    """
    return dict(form=auth())

# ---- action to server uploaded static content (required) ---
@cache.action()
def download():
    """
    allows downloading of uploaded files
    http://..../[app]/default/download/[filename]
    """
    return response.download(request, db)
