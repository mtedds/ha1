
import sqlite3
from datetime import datetime
import os.path


# This function is used to convert times (HH:MM:SS) to seconds
def timeConvert(inTime):
    # Commented out as this could impact database performance
    # self.logger.debug(f"database timeConvert {inTime}")
    numbers = inTime.split(":")
    return (int(numbers[0])*60 + int(numbers[1])) * 60 + int(numbers[2])


class Database:
    # TODO: Database name / location needs to be in a constants import
    # to support web2py use of this class (then doesn't need to be an argument here

    def __init__(self, inDatabaseFilename, inLogger):
        self.logger = inLogger
        self.logger.debug(f"database __init__ {inDatabaseFilename}")

        # Set the lock timeout to 5 seconds, which is the default
        self.dbConnection = sqlite3.connect(inDatabaseFilename, timeout=5)
        self.dbConnection.row_factory = sqlite3.Row

        self.dbConnection.create_function("to_seconds", 1, timeConvert)

        # TODO Parameterise the history database
        history_database_name = f"{os.path.dirname(inDatabaseFilename)}/controller_history.db"
        self.dbConnection.execute(f"attach database '{history_database_name}' as 'history'")

    def getLastSeconds(self):
        self.logger.debug(f"database getLastSeconds")
        cursor = self.dbConnection.cursor()
        cursor.execute(
                """select Value
                from State
                where Name = "LastSeconds"
                """
                )
        row = cursor.fetchone()
        cursor.close()
        return row[0]

    def setLastSeconds(self, inLastSeconds):
        self.logger.debug(f"database setLastSeconds {inLastSeconds}")
        cursor = self.dbConnection.cursor()
        cursor.execute(
                """Update State
                set Value = ?
                where Name = "LastSeconds"
                """,
                (inLastSeconds,)
                )
        cursor.close()
        self.dbConnection.commit()
        return 0

    def gatewayNames(self):
        self.logger.debug(f"database gatewayNames")
        return [name[0] for name in self.dbConnection.execute("select GatewayName from gateway").fetchall()]

    def gatewayIds(self):
        self.logger.debug(f"database gatewayIds")
        return [name[0] for name in self.dbConnection.execute("select GatewayId from gateway").fetchall()]

    def gatewaySubscribes(self):
        self.logger.debug(f"database gatewaySubscribes")
        return [name[0] for name in self.dbConnection.execute("select SubscribeTopic from gateway").fetchall()]

    def gatewayPublishes(self):
        self.logger.debug(f"database gatewayPublishes")
        return [name[0] for name in self.dbConnection.execute("select PublishTopic from gateway").fetchall()]

    def gatewayFindFromSubscribeTopic(self, inSubscribeTopic):
        self.logger.debug(f"database gatewayFindFromSubscribeTopic {inSubscribeTopic}")
        cursor = self.dbConnection.cursor()
        cursor.execute(
                """select GatewayId, GatewayName,
                BrokerHost, ClientId,
                SubscribeTopic, PublishTopic,
                Username, Password, LastSeen
                from Gateway
                where SubscribeTopic = ?""",
                (inSubscribeTopic,))
        row = cursor.fetchone()
        cursor.close()
        return row

    def nodeFindFromMyNode(self, inGatewayId, inMyNode):
        self.logger.debug(f"database nodeFindFromMyNode {inGatewayId}, {inMyNode}")
        # Should probably do something if find more than one...
        cursor = self.dbConnection.cursor()
        cursor.execute(
                """select ifnull(max(nodeid), -1) as NodeId
                from Node
                where GatewayId = ?
                and MySensorsNodeId = ?""",
                (inGatewayId, inMyNode))
        row = cursor.fetchone()
        cursor.close()
        return row["NodeId"]

    def sensorFindFromMySensor(self, inNodeId, inMySensor):
        self.logger.debug(f"database sensorFindFromMySensor {inNodeId}, {inMySensor}")
        # Should probably do something if find more than one...
        cursor = self.dbConnection.cursor()
        cursor.execute(
                """select ifnull(max(SensorId), -1)
                from Sensor
                where NodeId = ?
                and MySensorsSensorId = ?""",
                (inNodeId, inMySensor))
        row = cursor.fetchone()
        cursor.close()
        return row[0]

    def getNextId(self, inTable):
        self.logger.debug(f"database getNextId {inTable}")
        # Find the next Id for a generic table - start at 1
        cursor = self.dbConnection.cursor()
        sql = "select ifnull(max("+inTable+"id) + 1, 1) from "+inTable
        cursor.execute(sql)
        row = cursor.fetchone()
        cursor.close()
        return row[0]

    # Creates a new node row with the values provided (generates the Id column)
    # Also updates the last seen date time
    def object_create(self, inTable, inValues):
        self.logger.debug(f"database object_create {inTable}, {inValues}")
        sql1 = "insert into " + inTable + " (" + inTable + "Id,"
        sql2 = " values (?,"
        for column in inValues.keys():
            sql1 = sql1 + column + ","
            sql2 = sql2 + "?,"
        sql1 = sql1 + "LastSeen)"
        sql2 = sql2 + "strftime('%s', 'now'))"
        vals = list(inValues.values())
        nextObjectId = self.getNextId(inTable)
        vals.insert(0, nextObjectId)
        cursor = self.dbConnection.cursor()
        cursor.execute(sql1 + sql2, vals)
        self.dbConnection.commit()
        cursor.close()
        return nextObjectId

    def object_delete(self, in_table, in_key_value):
        cursor = self.dbConnection.cursor()
        cursor.execute(
            f"""delete from {in_table}
                    where {in_table}Id = ?
                    """,
            (in_key_value, ))
        cursor.close()

    def object_find(self, in_table, in_filters):
        # Simple search in the table using the provided dict as filters
        self.logger.debug(f"database object_find {in_table}, {in_filters}")
        sql = f"select * from {in_table} where "
        for column in in_filters.keys():
            sql = sql + column + " =? and "
        # Chop off the final "and"
        sql = sql[:-5]
        vals = list(in_filters.values())
        self.logger.debug(f"database object_find {sql}, {vals}")
        cursor = self.dbConnection.cursor()
        cursor.execute(sql, vals)
        rows = cursor.fetchall()
        self.dbConnection.commit()
        cursor.close()
        return rows

    def object_update(self, inTable, inKeyValue, inUpdates):
        # Takes a key field value with a set of updates and applies to the node row
        # Assumes key column name is "Table"Id, eg. NodeId
        # Also updates the last seen date time
        self.logger.debug(f"database object_update {inTable}, {inKeyValue}, {inUpdates}")
        sql = "update " + inTable + " set "
        for column in inUpdates.keys():
            sql = sql + column + "=?,"
        sql = sql + "LastSeen = strftime('%s', 'now') "
        sql = sql + "where " + inTable + "id=?"
        vals = list(inUpdates.values())
        vals.append(inKeyValue)
        cursor = self.dbConnection.cursor()
        cursor.execute(sql, vals)
        self.dbConnection.commit()
        cursor.close()
        return 0

    # Check if the node exists and create if not
    # We are only provided the owning Gateway and MySensors Node Id
    def nodeCreateUpdate(self, inGatewayId, inMyNode, inValues):
        self.logger.debug(f"database nodeCreateUpdate {inGatewayId}, {inMyNode}, {inValues}")
        nodeFound = self.nodeFindFromMyNode(inGatewayId, inMyNode)
        if nodeFound >= 0:
            self.object_update("Node", nodeFound, inValues)
        elif nodeFound == -1:
            nodeFound = self.object_create("Node", inValues)
        return nodeFound

    # Check if the sensor exists and create if not
    # We are only provided the owning NodeId and MySensors Sensor Id
    def sensor_create_update(self, inNodeId, inMySensor, inValues):
        self.logger.debug(f"database sensor_create_update {inNodeId}, {inMySensor}, {inValues}")
        sensor_found = self.sensorFindFromMySensor(inNodeId, inMySensor)
        if sensor_found >= 0:
            self.object_update("Sensor", sensor_found, inValues)
        elif sensor_found == -1:
            sensor_found = self.object_create("Sensor", inValues)

        self.dbConnection.execute(
            f"""insert into history.sensor_history (SensorId, Value, Time)
                select sensorid, currentvalue, lastseen
                from sensor where sensorId = {sensor_found}
             """)

        return sensor_found

    def find_sensor_by_name(self, inSensorName):
        self.logger.debug(f"database find_sensor_by_name {inSensorName}")
        cursor = self.dbConnection.cursor()
        cursor.execute(
                """select SensorName, PublishTopic, SubscribeTopic, MySensorsNodeId, MySensorsSensorId, VariableType, Node.NodeId
                from Gateway, Node, Sensor
                where SensorName = ?
                and Sensor.NodeId = Node.NodeId
                and Node.GatewayId = Gateway.GatewayId""",
                (inSensorName,))
        row = cursor.fetchone()
        cursor.close()

        return row

    def get_sensor_value_by_name(self, in_sensor_name):
        self.logger.debug(f"database get_sensor_value_by_name {in_sensor_name}")
        cursor = self.dbConnection.cursor()
        cursor.execute(
            """select ifnull(CurrentValue, "") as currentvalue
            from Sensor
            where SensorName = ?""",
            (in_sensor_name,))
        row = cursor.fetchone()
        cursor.close()
        return row["currentvalue"]

    def timed_actions_fired(self, in_day_number, inStartSeconds, inEndSeconds):
        self.logger.debug(f"database timed_actions_fired {in_day_number} {inStartSeconds}, {inEndSeconds}")
        cursor = self.dbConnection.cursor()
        cursor.execute(
                """select Action.ActionId, Action.SensorName, Action.VariableType, Action.SetValue
                , Action.TimedTriggerToUpdate
                , TimedTrigger.TimedTriggerID, TimedTrigger.Status
                , TimedTrigger.Description Description
                , TimedTrigger.Time
                , CASE WHEN TimedTrigger.Day < 0 then ?
                       ELSE TimedTrigger.Day END Day
                from TimedTrigger, Action
                where TimedTrigger.ActionId = Action.ActionId
                and TimedTrigger.Day in (-1, ?)
                and to_seconds(Time) between ? and ?
                order by to_seconds(Time), TimedTrigger.TimedTriggerId
                """,
                (in_day_number, in_day_number, inStartSeconds, inEndSeconds))
        actions = cursor.fetchall()
        cursor.close()
        return actions

    def nextTriggerTime(self, inSeconds):
        self.logger.debug(f"database nextTriggerTime {inSeconds}")

        current_day_of_week = datetime.now().weekday()

        cursor = self.dbConnection.cursor()
        # If cannot find anything, return 24 hours (ie max + 1)
        cursor.execute(
                """select ifnull(min(to_seconds(TimedTrigger.Time)), 86400) as Seconds
                from TimedTrigger
                where to_seconds(TimedTrigger.Time) > ?
                and day in (-1, ?)
                and Status in ("Active", "Once", "Replace")
                order by to_seconds(TimedTrigger.Time) asc
                """,
                (inSeconds, current_day_of_week))
        seconds = cursor.fetchone()
        cursor.close()
        return seconds["Seconds"]

    def hp_is_on(self, in_sensor):
        self.logger.debug(f"database hp_is_on {in_sensor}")

        if in_sensor == "HC":
            if int(self.get_sensor_value_by_name("Operating Mode")) == 5:
                return False

        interval = self.current_relay_interval(in_sensor)

        if interval[0]["SetValue"] == "0":
            return False
        else:
            return True

    def get_DHW_interval(self, in_day):
        self.logger.debug(f"database get_DHW_interval {in_day}")
        cursor = self.dbConnection.cursor()
        cursor.execute(
            f"""select Time, SetValue, TimedTriggerId
                    from TimedTrigger, Action
                    where Day = ?
                    and SensorName = "DHW"
                    and Status = "External"
                    and TimedTrigger.ActionId = Action.ActionId
                    order by to_seconds(Time)""",
            (in_day,))
        trigger_times = cursor.fetchall()
        cursor.close()

        return trigger_times

    # This finds the timed trigger entry for the sensor
    def current_relay_interval(self, in_sensor_name):
        self.logger.debug(f"database current_relay_interval {in_sensor_name}")

        # This handles manual switch - but HC and DHW are not sensors...
        if in_sensor_name in {"HC", "DHW"}:
            current_value = -1
        else:
            current_value = self.get_sensor_value_by_name(in_sensor_name)

        return self.current_relay_interval_value(in_sensor_name, current_value)

    def current_relay_interval_value(self, in_sensor_name, in_value):
        self.logger.debug(f"database current_relay_interval_value {in_sensor_name} {in_value}")

        # This is pretty painful when we introduced Once triggers.
        # It will pick up a Once trigger as a start point (eg, we are currently in a "boost" interval)
        # and also understand "masking" where a Once on value masks a permanent off value, for instance.

        now = datetime.now()
        # Monday is zero in both cases
        current_day_of_week = now.weekday()
        current_time = now.hour * 60 + now.minute

        cursor = self.dbConnection.cursor()
        # Note Once is alphabetically before Active in a descending sort - need to find Once triggers before Active
        cursor.execute(
            f"""select SetValue
            , case Day when -1 then {current_day_of_week} else Day end Day
            , Time
            , SetValue
            , Status
            , TimedTriggerId
            , TimedTrigger.Description
            from Action, TimedTrigger
            where SensorName = ?
            and TimedTrigger.ActionId = Action.ActionId
            and TimedTrigger.Status in ("Active", "External", "Once")
            order by Day, to_seconds(Time), Status desc""",
            (in_sensor_name, ))
        trigger_times = cursor.fetchall()
        cursor.close()

        # If don't find any, return nothing here
        if len(trigger_times) == 0:
            return {}

        # Prime the previous trigger just in case we are early on Monday morning
        # - set it to the very last trigger in the week (last on Sunday)
        return_triggers = {0: trigger_times[len(trigger_times)-1]}

        # This is set when we process a Once trigger that is masking an Active trigger at the same time
        ignore_next = False

        # This is set if we find a trigger at midnight (23:59:59)
        # and we need to check if the next trigger switches it back
        midnight = False

        # Search for today
        for trigger in trigger_times:
            # If last switch was 23:59:59 and this is 00:00:00 it must be an external interval over midnight
            if midnight and trigger["Time"] == "00:00:00":
                ignore_next = True
            if trigger["Day"] == current_day_of_week:
                if current_time < int(trigger["Time"][0:2]) * 60 + int(trigger["Time"][3:5]):
                    if trigger["SetValue"] != in_value and not ignore_next:
                        return_triggers[1] = trigger
                        if not trigger["Time"] == "23:59:59":
                            return return_triggers
                    # We have found a masking Once trigger
                    elif trigger["SetValue"] == in_value and trigger["Status"] == "Once":
                        ignore_next = True
                    else:
                        ignore_next = False
            elif trigger["Day"] == current_day_of_week + 1:
                # Moved on to tomorrow
                if trigger["SetValue"] != in_value and not ignore_next:
                    return_triggers[1] = trigger
                    return return_triggers
                # We have found a masking Once trigger
                elif trigger["SetValue"] == in_value and trigger["Status"] == "Once":
                    ignore_next = True
                else:
                    ignore_next = False
            if trigger["Time"] == "23:59:59":
                midnight = True
            # Move the prior trigger on if it actually set it to the current value
            # - or use it anyway if we have come in with a -1 value (just find current interval)
            if (trigger["SetValue"] == in_value or in_value == -1) and not midnight:
                return_triggers[0] = trigger


        # Must be end of Sunday so next trigger is first thing on Monday
        return_triggers[1] = trigger_times[0]
        return return_triggers

    def next_relay_switch_time(self, in_sensor_name):
        self.logger.debug(f"database next_relay_switch_time {in_sensor_name}")

        return self.current_relay_interval(in_sensor_name)[1]["Time"]

    def next_relay_switch_time_value(self, in_sensor_name, in_value):
        self.logger.debug(f"database next_relay_switch_time_value {in_sensor_name} {in_value}")

        # Might not return anything if there are no intervals for the sensor
        currentInterval = self.current_relay_interval_value(in_sensor_name, in_value)
        if len(currentInterval) == 0:
            return {}
        return currentInterval[1]["Time"]

    def find_triggers_until(self, in_sensor_name, in_start_time, in_end_time):
        # Find all the triggers against this sensor from start time until the end time is passed
        # Could cross midnight...
        self.logger.debug(f"database find_triggers_until {in_sensor_name} {in_start_time} {in_end_time}")

        if len(in_start_time) < 8:
            in_start_time += ":00"
        if len(in_end_time) < 8:
            in_end_time += ":00"

        start_seconds = timeConvert(in_start_time)
        end_seconds = timeConvert(in_end_time)

        now = datetime.now()
        # Monday is zero in both cases
        current_day_of_week = now.weekday()

        if start_seconds < end_seconds:
            # Simple case - not crossing midnight!
            cursor = self.dbConnection.cursor()

            cursor.execute(
                f"""select SetValue
                        , case Day when -1 then {current_day_of_week} else Day end Day
                        , Time
                        from Action, TimedTrigger
                        where SensorName = ?
                        and TimedTrigger.ActionId = Action.ActionId
                        and Day in (-1, ?)
                        and to_seconds(Time) between ? and ?
                        order by to_seconds(Time)""",
                (in_sensor_name, current_day_of_week, start_seconds, end_seconds))
            trigger_times = cursor.fetchall()
            cursor.close()

            return trigger_times

        if start_seconds < end_seconds:
            first_end_seconds = end_seconds
        else:
            first_end_seconds = 86400

        # Crossed midnight so find tomorrow's actions
        tomorrow = (current_day_of_week + 1) % 7

        cursor = self.dbConnection.cursor()
        cursor.execute(
            f"""select SetValue
                        , case Day when -1 then {current_day_of_week} else Day end Day
                        , Time
                        , to_seconds(Time) seconds
                        from Action, TimedTrigger
                        where SensorName = ?
                        and TimedTrigger.ActionId = Action.ActionId
                        and Day in (-1, ?)
                        and to_seconds(Time) between ? and 86400
                union all
                select SetValue
                           , case Day when -1 then {tomorrow} else Day end Day
                           , Time
                           , to_seconds(Time) seconds
                           from Action, TimedTrigger
                           where SensorName = ?
                           and TimedTrigger.ActionId = Action.ActionId
                           and Day in (-1, ?)
                           and to_seconds(Time) between 0 and ?
                order by seconds""",
            (in_sensor_name, current_day_of_week, start_seconds, in_sensor_name, tomorrow, end_seconds))
        trigger_times = cursor.fetchall()
        cursor.close()

        return trigger_times

    def create_once_trigger(self, in_sensor_name, in_day, in_time, in_value):
        # Create a once trigger to set the sensor to the value on the day / time specified
        self.logger.debug(f"database create_once_trigger {in_sensor_name} {in_day} {in_time} {in_value}")

        self.create_trigger(in_sensor_name, in_day, in_time, in_value, "Once", f"{in_sensor_name} Temporary")

    def create_replace_trigger(self, in_sensor_name, in_day, in_time, in_timed_trigger_id):
        # Create a Replace trigger to reset the sensor to the regular time
        self.logger.debug(
            f"database create_replace_trigger {in_sensor_name} {in_day} {in_time} {in_timed_trigger_id}")

        # Find the current time for the trigger
        search_filter = {"TimedTriggerId": in_timed_trigger_id}
        timed_trigger = self.object_find("TimedTrigger", search_filter)

        # First create the Action to replace the time
        values = {"TimedTriggerToUpdate": in_timed_trigger_id,
                  "SensorName": in_sensor_name,
                  "SetValue": timed_trigger[0]["Time"]
                  }
        new_action_id = self.object_create("Action", values)

        values = {"Time": in_time,
                  "ActionId": new_action_id,
                  "Description": f"{in_sensor_name} Temporary",
                  "Day": in_day,
                  "Status": "Replace"
                  }
        self.object_create("TimedTrigger", values)

    def create_trigger(self, in_sensor_name, in_day, in_time, in_value, in_type, in_description):
        self.logger.debug(f"database create_trigger {in_sensor_name} {in_day} {in_time} {in_value} {in_type} {in_description}")

        # Find an action that matches
        # TODO - what if there isn't an action!!!
        cursor = self.dbConnection.cursor()
        cursor.execute(
            """select min(ActionId) ActionId
                from Action
                where SensorName = ?
                and SetValue = ?""",
            (in_sensor_name, in_value))
        action = cursor.fetchone()
        cursor.close()
        self.logger.debug(action)

        if len(in_time) < 8:
            in_time += ":00"

        values = {"Time": in_time,
                  "ActionId": action["ActionId"],
                  "Description": in_description,
                  "Day": in_day,
                  "Status": in_type
                  }
        self.object_create("TimedTrigger", values)

    def delete_once_triggers(self, in_sensor):
        self.logger.debug(f"database delete_once_triggers {in_sensor}")
        cursor = self.dbConnection.cursor()
        cursor.execute(
            """delete from TimedTrigger
                    where ActionId in (
                        select ActionId
                        from Action
                        where SensorName = ?
                        )
                    and Status = "Once"
                    """,
            (in_sensor,))
        cursor.close()

    def delete_prefixed_triggers(self, in_prefix):
        self.logger.debug(f"database delete_prefix_triggers {in_prefix}")
        cursor = self.dbConnection.cursor()
        cursor.execute(
            """delete from TimedTrigger
                    where description like ?
                    and Status = "Once"
                    """,
            (f"{in_prefix}%",))
        cursor.close()

    def find_replace_triggers(self, in_sensor):
        # TODO implement day of the week!!!
        self.logger.debug(f"database find_replace_triggers {in_sensor}")
        cursor = self.dbConnection.cursor()
        cursor.execute(
                """select Action.ActionId, Action.SensorName, Action.VariableType, Action.SetValue
                , Action.TimedTriggerToUpdate
                , TimedTrigger.TimedTriggerID, TimedTrigger.Status
                , TimedTrigger.Description Description
                , TimedTrigger.Time, TimedTrigger.Day
                from TimedTrigger, Action
                where TimedTrigger.ActionId = Action.ActionId
                and Status = "Replace"
                and Action.SensorName = ?
                order by to_seconds(Time), TimedTrigger.TimedTriggerId
                """,
                (in_sensor, ))
        actions = cursor.fetchall()
        cursor.close()
        return actions

    def read_prog(self, in_sensor_name):
        self.logger.debug(f"database read_prog {in_sensor_name}")

        cursor = self.dbConnection.cursor()
        # Note that 7 is used as Daily
        cursor.execute(
            f"""select SetValue
                    , case Day when -1 then 7 else Day end Day
                    , Time
                    from Action, TimedTrigger
                    where SensorName = ?
                    and TimedTrigger.ActionId = Action.ActionId
                    and TimedTrigger.Status != "Once"
                    order by Day, to_seconds(Time)""",
            (in_sensor_name,))
        trigger_times = cursor.fetchall()
        cursor.close()

        return_triggers = {}
        day = -1

        for trigger in trigger_times:
            if int(trigger["Day"]) > day:
                day = int(trigger["Day"])
                return_triggers[day] = {}
                interval_count = 0

            return_triggers[day][interval_count] = {"Time": trigger["Time"], "SetValue": trigger["SetValue"]}
            interval_count += 1

        return return_triggers

    def get_prog_actionids(self, in_sensor):
        self.logger.debug(f"database get_prog_actionids {in_sensor}")

        cursor = self.dbConnection.cursor()
        cursor.execute(
            """select Action.ActionId
                    from Action
                    where Sensorname = ?
                    order by SetValue
                    """,
            (in_sensor, ))
        actions = cursor.fetchall()
        cursor.close()

        return {0: actions[0]["actionid"], 1: actions[1]["actionid"]}

    def clear_old_timed_triggers(self, in_sensor, in_actionids):
        self.logger.debug(f"database clear_old_timed_triggers {in_sensor} {in_actionids}")

        cursor = self.dbConnection.cursor()
        cursor.execute(
            """delete from TimedTrigger
                    where ActionId in (?, ?)
                    """,
            (in_actionids[0], in_actionids[1]))
        cursor.close()

    def update_trigger(self, in_sensor, in_day, in_group, in_value, in_time):
        self.logger.debug(f"database update_trigger {in_sensor} {in_day} {in_group} {in_value} {in_time}")

        # Message from UI to modify a timed trigger for one of the programmes
        # TODO Add group as a column to the timedtrigger table to avoid the fuzzy match

        sql = f"""update timedtrigger set time = ?
                    where timedtriggerid = 
                      (select timedtriggerid from timedtrigger, action
                       where timedtrigger.actionid = action.actionid
                         and action.sensorname = ?
                         and action.setvalue = ?
                         and timedtrigger.status in ('Active', 'External')
                         and timedtrigger.day = ?
                         and timedtrigger.description like '%{in_group}%')
        """

        cursor = self.dbConnection.cursor()
        cursor.execute(sql, (in_time, in_sensor, in_value, in_day))
        self.dbConnection.commit()
        cursor.close()

    def switch_triggers(self, in_sensor, in_value):
        self.logger.debug(f"database switch_triggers {in_sensor} {in_value}")

        # Update all the ON triggers for a particular sensor to be inactive / active

        sql = f"""update timedtrigger set status = ?
                    where timedtriggerid in
                      (select timedtriggerid from timedtrigger, action
                       where timedtrigger.actionid = action.actionid
                         and action.sensorname = ?
                         and action.setvalue = 1)
        """

        cursor = self.dbConnection.cursor()
        cursor.execute(sql, (in_value, in_sensor))
        self.dbConnection.commit()
        cursor.close()

    def store_prog(self, in_sensor, in_intervals):
        self.logger.debug(f"database store_prog {in_sensor} {in_intervals}")

        days_of_the_week = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}

        actions = self.get_prog_actionids(in_sensor)
        self.clear_old_timed_triggers(in_sensor, actions)

        values = {"Status": "External"}

        for day in range(7):
            values["Day"] = day
            for interval in in_intervals[day].keys():
                trigger_desc = f"{in_sensor} Prog {days_of_the_week[day]} {interval} "

                if in_intervals[day][interval][0] != "32:00":
                    values["Description"] = trigger_desc + "on"
                    values["Time"] = in_intervals[day][interval][0] + ":00"
                    values["ActionId"] = actions[1]
                    self.object_create("TimedTrigger", values)

                    values["Description"] = trigger_desc + "off"
                    values["Time"] = in_intervals[day][interval][1] + ":00"
                    values["ActionId"] = actions[0]
                    self.object_create("TimedTrigger", values)

    def read_all_sensors(self):
        self.logger.debug(f"database read_all_sensors")

        cursor = self.dbConnection.cursor()
        cursor.execute(
            """select SensorName, CurrentValue
                    from Sensor
                    """)
        sensor_values = cursor.fetchall()
        cursor.close()

        sensor_dict = {}
        for sensor in sensor_values:
            sensor_dict[sensor["SensorName"]] = sensor["CurrentValue"]

        return sensor_dict

    def read_savingsession(self):
        self.logger.debug(f"database read_savingsession")

        cursor = self.dbConnection.cursor()
        cursor.execute(
            """select Day, Time
                    from TimedTrigger
                    where Description like 'SS %'
                    group by Day, Time
                    order by Day, Time
                    """)
        times = cursor.fetchall()
        cursor.close()

        if len(times) < 1:
            return {}
        elif len(times) == 1:
            return {"dayofweek": times[0]["Day"], "starttime": times[0]["Time"], "endtime": times[0]["Time"]}
        if len(times) == 2:
            return {"dayofweek": times[0]["Day"], "starttime": times[0]["Time"], "endtime": times[1]["Time"]}
        else:
            return {}
