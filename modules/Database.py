
import sqlite3


class Database:

    def __init__(self, inDatabaseFilename, inLogger):
        self.logger = inLogger
        self.logger.debug(f"database __init__ {inDatabaseFilename}")

        # Set the lock timeout to 5 seconds, which is the default
        self.dbConnection = sqlite3.connect(inDatabaseFilename, timeout=5)
        self.dbConnection.row_factory = sqlite3.Row

        self.dbConnection.create_function("to_seconds", 1, self.timeConvert)

        # This function is used to convert times (HH:MM:SS) to seconds
    def timeConvert(self, inTime):
        # Commented out as this could impact database performance
        #self.logger.debug(f"database timeConvert {inTime}")
        numbers = inTime.split(":")
        return (int(numbers[0])*60 + int(numbers[1])) * 60 + int(numbers[2])

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
        self.logger.debug(f"database gatewayFindFromSubscribeTopic {inSubscribeTopic} = {row}")
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
    def objectCreate(self, inTable, inValues):
        self.logger.debug(f"database objectCreate {inTable}, {inValues}")
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

    # Takes a key field value with a set of updates and applies to the node row
    # Assumes key column name is "Table"Id, eg. NodeId
    # Also updates the last seen date time
    def objectUpdate(self, inTable, inKeyValue, inUpdates):
        self.logger.debug(f"database objectUpdate {inTable}, {inKeyValue}, {inUpdates}")
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
            self.objectUpdate("Node", nodeFound, inValues)
        elif nodeFound == -1:
            nodeFound = self.objectCreate("Node", inValues)
        return nodeFound

    # Check if the sensor exists and create if not
    # We are only provided the owning NodeId and MySensors Sensor Id
    def sensorCreateUpdate(self, inNodeId, inMySensor, inValues):
        self.logger.debug(f"database sensorCreateUpdate {inNodeId}, {inMySensor}, {inValues}")
        sensorFound = self.sensorFindFromMySensor(inNodeId, inMySensor)
        if sensorFound >= 0:
            self.objectUpdate("Sensor", sensorFound, inValues)
            return 1
        elif sensorFound == -1:
            sensorFound = self.objectCreate("Sensor", inValues)
        return sensorFound

    def findSensorByName(self, inSensorName):
        self.logger.debug(f"database findSensorByName {inSensorName}")
        cursor = self.dbConnection.cursor()
        cursor.execute(
                """select PublishTopic, MySensorsNodeId, MySensorsSensorId, VariableType
                from Gateway, Node, Sensor
                where SensorName = ?
                and Sensor.NodeId = Node.NodeId
                and Node.GatewayId = Gateway.GatewayId""",
                (inSensorName,))
        row = cursor.fetchone()
        cursor.close()
        return row

    def timedActionsFired(self, inStartSeconds, inEndSeconds):
        self.logger.debug(f"database timedActionsFired {inStartSeconds}, {inEndSeconds}")
        cursor = self.dbConnection.cursor()
        cursor.execute(
                """select Action.ActionId, Action.SensorName, Action.VariableType, Action.SetValue
                from TimedTrigger, Action
                where TimedTrigger.ActionId = Action.ActionId
                and to_seconds(Time) between ? and ?
                order by to_seconds(Time), TimedTrigger.ActionId
                """,
                (inStartSeconds, inEndSeconds))
        actions = cursor.fetchall()
        cursor.close()
        return actions

    def nextTriggerTime(self, inSeconds):
        self.logger.debug(f"database nextTriggerTime {inSeconds}")
        cursor = self.dbConnection.cursor()
        # If cannot find anything, return 24 hours (ie max + 1)
        cursor.execute(
                """select ifnull(min(to_seconds(TimedTrigger.Time)), 86400) as Seconds
                from TimedTrigger
                where to_seconds(TimedTrigger.Time) > ?
                order by to_seconds(TimedTrigger.Time) asc
                """,
                (inSeconds,))
        seconds = cursor.fetchone()
        cursor.close()
        return seconds["Seconds"]
