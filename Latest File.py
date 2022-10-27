import time
import pytz
from tkinter import *
from tkinter import ttk
from tkinter import messagebox
from typing import Dict, Type
from requests.models import HTTPError
from tkcalendar import *

import pymongo
import json
import smtplib
import requests
from datetime import datetime, timedelta, timezone, date
import threading
from td.oauth import callback
from config import CUSTOMER_KEY, CALLBACK_URL, JSON_PATH, MARKOUT_URL, MARKOUT_NAME
from td.client import TDClient
from td.orders import Order, OrderLeg
from td.enums import ORDER_SESSION, DURATION, ORDER_INSTRUCTIONS, ORDER_ASSET_TYPE, ORDER_STRATEGY_TYPE, ORDER_TYPE
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
# Get current Quotes


class Root(Tk):
    def __init__(self):
        super(Root, self).__init__()
        self.title("AY Stock")
        self.SymbolDBName = "TD_TRADE"
        MARKOUT_NAME.sort()
        window_width = 1280
        window_height = 670
        self.minsize(window_width, window_height)
        self.screen_width = self.winfo_screenwidth()
        self.screen_height = self.winfo_screenheight()
        self.geometry(
            "%dx%d+%d+%d"
            % (
                window_width,
                window_height,
                self.screen_width / 2 - window_width / 2,
                self.screen_height / 2 - window_height / 2,
            )
        )

        # Create a new instance from client
        self.newyork_timezone = pytz.timezone('US/Eastern')
        self.utc_timezone = pytz.timezone('UTC')
        self.tdInstance = TDClient(
            client_id=CUSTOMER_KEY, redirect_uri=CALLBACK_URL, credentials_path=JSON_PATH)

        # Create log file
        LOG_FILENAME = datetime.now(self.newyork_timezone).strftime(
            './logs/log_%m_%d_%Y.log')
        logging.basicConfig(filename=LOG_FILENAME, level=logging.INFO)
        self.requestInterval = 0.5
        self.requestCheckInterval = 0.05

        # Login a new seesion
        self.tdInstance.login()
        # accounts = self.tdInstance.get_accounts()
        # print(accounts)

        # send email
        self.gmail_user = 'xxxxxxxx@gmail.com'
        self.gmail_password = 'xxxxx'
        self.sent_from = "td@mail.com"

        # callmebot url
        # "https://api.callmebot.com/whatsapp.php?phone=+2348107937955&apikey=883369&text="
        self.signalURL = "https://api.callmebot.com/signal/send.php?phone=+96891496284&apikey=762916&text="

        todayDateTime = datetime.now(self.newyork_timezone)  # .weekday()
        print("Weekday", todayDateTime.weekday())
        print("Oclock", todayDateTime.hour)
        print("Minute", todayDateTime.minute)

        # db connection
        self.threadList = {}
        self.threadStateList = {}
        self.startegyParametersList = {}
        self.tdOrderStateList = {}
        self.tdOrderStateList4pm = None
        self.year = ""
        self.month = ""
        self.date = ""
        self.enterDate = 458
        self.dbClient = pymongo.MongoClient()
        self.lastAPICallTime = datetime.now().timestamp()
        # self.checkOrderTime()
        self.initTabs()
        self.addViewInStrategyList()
        self.addControllButtonsInStrategyList()
        self.addViewInNewManage()
        self.addButtonsInNewManage()
        self.addViewInLive()

        refreshTokenThread = threading.Thread(
            target=self.checkAndRefreshToken,
            daemon=True
        )
        refreshTokenThread.start()
        getTDOrderHistoryThread = threading.Thread(
            target=self.getOrderHistoryFromTD,
            daemon=True
        )
        getTDOrderHistoryThread.start()

        self.logInfo("App strated")

    def logError(self, logTxt):
        dateTime = datetime.now(
            self.newyork_timezone).strftime('%Y-%m-%d %H:%M:%S')
        logging.error(" "+logTxt+" "+dateTime)

    def logInfo(self, logTxt):
        dateTime = datetime.now(
            self.newyork_timezone).strftime('%Y-%m-%d %H:%M:%S')
        logging.info(" "+logTxt+" "+dateTime)

    def checkAndRefreshToken(self):
        while True:
            time.sleep(1200)
            print("refresh token")
            while True:
                currentTimeStamp = datetime.now().timestamp()
                if (currentTimeStamp - self.lastAPICallTime) >= self.requestInterval:
                    self.lastAPICallTime = currentTimeStamp
                    self.logInfo("refresh token")
                    try:
                        self.tdInstance.grab_access_token()
                        break
                    except Exception as e:
                        print(e)
                        self.logError("Token refresh has error " + str(e))
                time.sleep(self.requestCheckInterval)

    def getOrderHistoryFromTD(self):
        count = 0
        while True:
            time.sleep(15)
            count += 1
            count = count % 2
            if count != 0 or self.checkOrderTime("Root") != 0:
                continue
            accountIds = {}
            print("get TD history")
            currentTimestamp = datetime.now().timestamp()
            currentDate = datetime.fromtimestamp(
                int(currentTimestamp-self.enterDate*24*3600), tz=self.newyork_timezone
            )
            enterFromDate = currentDate.strftime("%Y-%m-%d")
            currentDate = datetime.fromtimestamp(
                int(currentTimestamp+24*3600), tz=self.newyork_timezone
            )
            enterToDate = currentDate.strftime("%Y-%m-%d")
            for key, value in self.accountIds.items():
                print("get TD history of account ID: ", value)
                self.logInfo("Get TD history of account ID:" + value)
                while True:
                    currentTimeStamp = datetime.now().timestamp()
                    if (currentTimeStamp - self.lastAPICallTime) >= self.requestInterval:
                        self.lastAPICallTime = currentTimeStamp
                        self.logInfo("get orders")
                        try:
                            orderHistory = self.tdInstance.get_orders_query(
                                account=value, to_entered_time=enterToDate, from_entered_time=enterFromDate)  # get all order list from TD
                            self.tdOrderStateList[value] = orderHistory
                        except Exception as e:
                            print(e)
                            # send email
                            body = 'Hi Abdullahi, Getting TD history has failed for account ID = ' +\
                                value+'. ' + str(e)
                            self.logError(body)
                            message = MIMEMultipart()
                            message['From'] = self.sent_from
                            message['To'] = "abeyusuf@gmail.com"
                            message['Subject'] = 'TD API Failed'
                            # save this issue in mongodb
                            content = {
                                'subject': message['Subject'],
                                'content': body,
                                'created_at':  datetime.today().strftime('%Y-%m-%d-%H:%M:%S')
                            }
                            stockDB = self.dbClient[self.SymbolDBName]
                            issueCollection = stockDB["Email"]
                            issueCollection.insert_one(
                                content)
                            # The body and the attachments for the mail
                            message.attach(
                                MIMEText(body, 'plain'))
                            try:
                                requests.get(
                                    self.signalURL+body.replace("#", ""))
                            except Exception as ex:
                                print("Signal went error", ex)
                                self.logError(
                                    "TD order history error Signal went error "+str(ex))
                            try:
                                smtp_server = smtplib.SMTP_SSL(
                                    'smtp.gmail.com', 465)
                                smtp_server.ehlo()
                                smtp_server.login(
                                    self.gmail_user, self.gmail_password)
                                email_text = message.as_string()
                                smtp_server.sendmail(
                                    self.sent_from, "abeyusuf@gmail.com", email_text)
                                smtp_server.close()
                                print(
                                    "Email sent successfully!")
                                self.logInfo(
                                    " TD order history error Email sent successfully!")
                            except Exception as ex:
                                print(
                                    "Email sending failed", ex)
                                self.logError(
                                    "TD order history error Email sending failed "+str(ex))
                        break
                    time.sleep(self.requestCheckInterval)
                time.sleep(1)

    def initTabs(self):
        tabControl = ttk.Notebook(self)
        self.tabStrategyListFrame = ttk.Frame(tabControl)
        tabControl.add(self.tabStrategyListFrame, text="Strategy")

        self.tabNewManageFrame = ttk.Frame(tabControl)
        tabControl.add(self.tabNewManageFrame, text="New Manage")

        self.tabLiveFrame = ttk.Frame(tabControl)
        tabControl.add(self.tabLiveFrame, text="Live")
        tabControl.pack(expand=1, fill="both")

    def on_closing(self):
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            root.destroy()

    # Strategy List
    def addViewInStrategyList(self):
        frame = Frame(self.tabStrategyListFrame)
        self.strategyTable = ttk.Treeview(
            frame, selectmode="browse", height=30)
        self.strategyTable["columns"] = (
            "Strategy", "Trades", "Profit($)", "Profit Factor", "Profitable(%)", "Strat Date", "Activate", "EntryAPI")
        self.strategyTable.column("#0", anchor=CENTER, width=40, minwidth=40)
        self.strategyTable.column("Strategy", anchor=CENTER, width=120)
        self.strategyTable.column("Trades", anchor=CENTER, width=60)
        self.strategyTable.column("Profit($)", anchor=CENTER, width=80)
        self.strategyTable.column("Profit Factor", anchor=CENTER, width=80)
        self.strategyTable.column("Profitable(%)", anchor=CENTER, width=60)
        self.strategyTable.column("Strat Date", anchor=CENTER, width=80)
        self.strategyTable.column("Activate", anchor=CENTER, width=60)
        self.strategyTable.column("EntryAPI", anchor=CENTER, width=400)

        self.strategyTable.heading("#0", text="ID", anchor=CENTER)
        self.strategyTable.heading("Strategy", text="Strategy", anchor=CENTER)
        self.strategyTable.heading("Trades", text="Trades", anchor=CENTER)
        self.strategyTable.heading(
            "Profit($)", text="Profit($)", anchor=CENTER)
        self.strategyTable.heading(
            "Profit Factor", text="Profit Factor", anchor=CENTER)
        self.strategyTable.heading(
            "Profitable(%)", text="Profitable(%)", anchor=CENTER)
        self.strategyTable.heading(
            "Strat Date", text="Strat Date", anchor=CENTER)
        self.strategyTable.heading("Activate", text="Activate", anchor=CENTER)
        self.strategyTable.heading("EntryAPI", text="EntryAPI", anchor=CENTER)

        yscrollbar = ttk.Scrollbar(
            frame, orient="vertical", command=self.strategyTable.yview
        )
        yscrollbar.pack(side=RIGHT, fill=Y)
        self.strategyTable.configure(yscrollcommand=yscrollbar.set)

        self.idArray = []
        self.strategyNamesArray = []
        self.strategyEntryAPIArray = []
        tdDB = self.dbClient[self.SymbolDBName]
        currentStrategyList = tdDB["strategy_list"].find()
        if currentStrategyList != None:
            iid = 0
            stockDB = self.dbClient[self.SymbolDBName]
            collection = stockDB["OrderList"]
            for item in currentStrategyList:
                myquery = {"strategyName": item["Strategy"], "state": "FILLED"}
                orderHistory = collection.find(myquery).sort(
                    "timestamp", pymongo.DESCENDING)
                totalProfit = 0
                sellFilledTrade = 0
                buyFilledTrade = 1
                profitTrade = 0
                minusAbsProfit = 0
                profitFactor = "0.0"
                if orderHistory != None:
                    # calculate the profit
                    for successedOrder in orderHistory:
                        # Sell Filled Order
                        if successedOrder["instruction"] == "SELL" or successedOrder["instruction"] == "BUY_TO_COVER":
                            if successedOrder["type"] == 0:  # long case
                                profit = float(successedOrder["filledPrice"])*float(successedOrder["filledQuantity"]) - float(
                                    successedOrder["boughtPrice"])*float(successedOrder["quantity"])
                            else:  # short case
                                profit = float(successedOrder["boughtPrice"])*float(successedOrder["quantity"]) - float(
                                    successedOrder["filledPrice"])*float(successedOrder["filledQuantity"])

                            if profit > 0:
                                profitTrade += 1
                            else:
                                minusAbsProfit += abs(profit)
                            totalProfit += profit
                            sellFilledTrade += 1
                        else:  # Buy Filled Order
                            buyFilledTrade += 1
                        if minusAbsProfit == 0:
                            profitFactor = "0.0"
                        else:
                            profitFactor = "{:.2f}".format(
                                totalProfit/minusAbsProfit)

                    self.strategyTable.insert(
                        parent="",
                        index="end",
                        iid=iid,
                        text=f"{iid+1}",
                        values=(
                            item["Strategy"],
                            str(buyFilledTrade-1),
                            "{:.4f}".format(totalProfit),
                            profitFactor,
                            "{:.2f}%".format(profitTrade/buyFilledTrade*100),
                            item["Start_Date"],
                            item["Activate"],
                            item["EntryAPI"],
                        ),
                    )
                else:
                    self.strategyTable.insert(
                        parent="",
                        index="end",
                        iid=iid,
                        text=f"{iid+1}",
                        values=(
                            item["Strategy"],
                            "0",
                            "0.0",
                            "0",
                            "0%",
                            item["Start_Date"],
                            item["Activate"],
                            item["EntryAPI"],
                        ),
                    )
                self.idArray.append(item["_id"])
                iid += 1
                if item["Activate"] == "Inactive":
                    continue
                self.strategyNamesArray.append(item["Strategy"])
                self.strategyEntryAPIArray.append(item["EntryAPI"])

        self.strategyTable.pack(side=LEFT, fill=X)
        frame.grid(row=0, column=0, rowspan=100,
                   columnspan=9, padx=10, pady=10)

    def onClickDashboardRefreshBtn(self):
        print("Refresh")
        self.strategyTable.delete(*self.strategyTable.get_children())
        tdDB = self.dbClient[self.SymbolDBName]
        currentStrategyList = tdDB["strategy_list"].find()
        if currentStrategyList != None:
            iid = 0
            stockDB = self.dbClient[self.SymbolDBName]
            collection = stockDB["OrderList"]
            for item in currentStrategyList:
                myquery = {"strategyName": item["Strategy"], "state": "FILLED"}
                orderHistory = collection.find(myquery).sort(
                    "timestamp", pymongo.DESCENDING)
                totalProfit = 0
                sellFilledTrade = 0
                buyFilledTrade = 1
                profitTrade = 0
                minusAbsProfit = 0
                profitFactor = "0.0"
                if orderHistory != None:
                    # calculate the profit
                    for successedOrder in orderHistory:
                        # Sell Filled Order
                        if successedOrder["instruction"] == "SELL" or successedOrder["instruction"] == "BUY_TO_COVER":
                            if successedOrder["type"] == 0:  # long case
                                profit = float(successedOrder["filledPrice"])*float(successedOrder["filledQuantity"]) - float(
                                    successedOrder["boughtPrice"])*float(successedOrder["quantity"])
                            else:  # short case
                                profit = float(successedOrder["boughtPrice"])*float(successedOrder["quantity"]) - float(
                                    successedOrder["filledPrice"])*float(successedOrder["filledQuantity"])

                            if profit > 0:
                                profitTrade += 1
                            else:
                                minusAbsProfit += abs(profit)
                            totalProfit += profit
                            sellFilledTrade += 1
                        else:  # Buy Filled Order
                            buyFilledTrade += 1
                        if minusAbsProfit == 0:
                            profitFactor = "0.0"
                        else:
                            profitFactor = "{:.2f}".format(
                                totalProfit/minusAbsProfit)

                    self.strategyTable.insert(
                        parent="",
                        index="end",
                        iid=iid,
                        text=f"{iid+1}",
                        values=(
                            item["Strategy"],
                            str(buyFilledTrade-1),
                            "{:.4f}".format(totalProfit),
                            profitFactor,
                            "{:.2f}%".format(profitTrade/buyFilledTrade*100),
                            item["Start_Date"],
                            item["Activate"],
                            item["EntryAPI"],
                        ),
                    )
                else:
                    self.strategyTable.insert(
                        parent="",
                        index="end",
                        iid=iid,
                        text=f"{iid+1}",
                        values=(
                            item["Strategy"],
                            "0",
                            "0.0",
                            "0",
                            "0%",
                            item["Start_Date"],
                            item["Activate"],
                            item["EntryAPI"],
                        ),
                    )
                iid += 1
                if item["Activate"] == "Inactive":
                    continue

    def addControllButtonsInStrategyList(self):
        addNewStrategyBtn = Button(
            self.tabStrategyListFrame,
            text="Add",
            width=12,
            command=self.onClickAddNewStrategyBtn,
        )
        addNewStrategyBtn.grid(row=0, column=9, padx=2, columnspan=2)
        changeActivateStateBtn = Button(
            self.tabStrategyListFrame,
            text="Active/Inactive",
            width=12,
            command=self.onClickChangeActiveBtn,
        )
        changeActivateStateBtn.grid(row=1, column=9, padx=2, columnspan=2)
        removeStrategyBtn = Button(
            self.tabStrategyListFrame,
            text="Delete",
            width=12,
            command=self.onClickDeleteStrategyBtn,
        )
        removeStrategyBtn.grid(row=2, column=9, padx=5, columnspan=2)
        refreshBtn = Button(
            self.tabStrategyListFrame,
            text="Refresh",
            width=12,
            command=self.onClickDashboardRefreshBtn,
        )
        refreshBtn.grid(row=3, column=9, padx=5, columnspan=2)

    def onClickAddNewStrategyBtn(self):
        self.showDialogToAddNewStrategy()

    def onClickChangeActiveBtn(self):
        selectedIndex = self.strategyTable.focus()
        if selectedIndex == "":
            messagebox.showerror(title=None, message="Please Select One")
            return
        selectedData = self.strategyTable.item(selectedIndex, 'values')
        print(selectedData[6])
        strategyName = selectedData[0]
        activeState = selectedData[6]
        if activeState == "Active":
            activeState = "Inactive"
        else:
            activeState = "Active"

        stockDB = self.dbClient[self.SymbolDBName]
        collection = stockDB["strategy_list"]
        myquery = {"Strategy": strategyName}
        newvalues = {"$set": {"Activate": activeState}}
        collection.update_one(myquery, newvalues)

        self.strategyTable.delete(
            *self.strategyTable.get_children())
        self.idArray = []
        self.strategyNamesArray = []
        self.strategyEntryAPIArray = []
        tdDB = self.dbClient[self.SymbolDBName]
        currentStrategyList = tdDB["strategy_list"].find()
        if currentStrategyList != None:
            iid = 0
            for item in currentStrategyList:
                self.strategyTable.insert(
                    parent="",
                    index="end",
                    iid=iid,
                    text=f"{iid+1}",
                    values=(
                        item["Strategy"],
                        item["Trades"],
                        item["Profit"],
                        item["Profit_Factor"],
                        item["Profitable"],
                        item["Start_Date"],
                        item["Activate"],
                        item["EntryAPI"],
                    ),
                )
                self.idArray.append(item["_id"])
                iid += 1
                if item["Activate"] == "Inactive":
                    continue
                self.strategyNamesArray.append(item["Strategy"])
                self.strategyEntryAPIArray.append(item["EntryAPI"])
        self.strategyComboBoxInLive["values"] = self.strategyNamesArray

        if self.selectedStrategy.get() != "" and self.selectedStrategy.get() not in self.strategyNamesArray:
            self.selectedStrategy.set("")

    def onClickDeleteStrategyBtn(self):
        selectedItem = self.strategyTable.focus()
        if selectedItem == "":
            messagebox.showerror(title=None, message="Please Select One")
            return
        strategyName = self.strategyTable.item(selectedItem)['values'][0]
        activeState = self.strategyTable.item(selectedItem)['values'][6]
        if activeState != "Inactive":
            messagebox.showerror(
                title=None, message="This strategy is acitve now.")
            return
        stockDB = self.dbClient[self.SymbolDBName]
        collection = stockDB["OrderList"]
        myquery = {"strategyName": strategyName}
        orderHistory = collection.count_documents(myquery)
        print(orderHistory)
        if orderHistory > 0:
            messagebox.showerror(
                title=None, message="This strategy has order history.")
            return

        collection = stockDB["strategy_list"]
        myquery = {"_id": self.idArray[int(selectedItem)]}
        collection.delete_one(myquery)

        self.strategyTable.delete(selectedItem)

    def showDialogToAddNewStrategy(self):
        global addNewStrategyDialog
        addNewStrategyDialog = Toplevel()
        addNewStrategyDialog.title("Add New Strategy")
        # addNewStrategyDialog.grab_set()
        window_width = 300
        window_height = 160
        addNewStrategyDialog.geometry(
            "%dx%d+%d+%d"
            % (
                window_width,
                window_height,
                self.screen_width / 2 - window_width / 2,
                self.screen_height / 2 - window_height / 2,
            )
        )

        strategyNameLabel = Label(
            addNewStrategyDialog, text="Enter Srategy Name")
        strategyNameLabel.grid(row=0, column=0, padx=10, pady=10)
        strategyNameEntry = Entry(addNewStrategyDialog, width=20)
        strategyNameEntry.grid(row=0, column=1, pady=10)
        strategyAPILabel = Label(addNewStrategyDialog,
                                 text="Enter Srategy API")
        strategyAPILabel.grid(row=1, column=0, padx=10, pady=10)
        strategyAPIEntry = Entry(addNewStrategyDialog, width=20)
        strategyAPIEntry.grid(row=1, column=1, pady=10)
        btnYes = Button(
            addNewStrategyDialog,
            text="  YES  ",
            command=lambda: self.addNewStrategy(
                strategyNameEntry.get(), strategyAPIEntry.get()),
        )
        btnYes.grid(row=2, column=0, columnspan=2, padx=10, pady=5)
        btnNo = Button(
            addNewStrategyDialog,
            text="  NO  ",
            command=lambda: addNewStrategyDialog.destroy(),
        )
        btnNo.grid(row=2, column=1, columnspan=2, padx=10, pady=5)

    def addNewStrategy(self, strategyName, strategyAPI):
        if strategyName == "":
            messagebox.showerror(
                title=None, message="Please Enter Strategy Name")
            return
        if strategyAPI == "":
            messagebox.showerror(
                title=None, message="Please Enter Strategy API")
            return
        if strategyName in self.strategyNamesArray:
            messagebox.showerror(
                title=None, message="This Strategy exists already")
            return
        currentDate = datetime.fromtimestamp(
            datetime.now().timestamp(), tz=self.newyork_timezone
        )
        currentDateStr = currentDate.strftime("%Y-%m-%d %H:%M")
        newStrategy = {
            "Strategy": strategyName,
            "Trades": 0,
            "Profit": 0,
            "Profit_Factor": "",
            "Profitable": "",
            "Start_Date": currentDateStr,
            "Activate": "Active",
            "EntryAPI": strategyAPI,
        }
        tdDB = self.dbClient[self.SymbolDBName]
        collection = tdDB["strategy_list"]
        new_strategy = collection.insert_one(newStrategy)
        newStrategy['_id'] = new_strategy.inserted_id
        self.idArray.append(new_strategy)
        self.strategyNamesArray.append(strategyName)
        self.strategyEntryAPIArray.append(strategyAPI)
        self.strategyComboBoxInLive["values"] = self.strategyNamesArray
        iid = len(self.strategyTable.get_children())
        self.strategyTable.insert(
            parent="",
            index="end",
            iid=iid,
            text=f"{iid+1}",
            values=(strategyName, 0, 0, "", "", currentDateStr,
                    "", "", 0, 0, "", "", "Active", strategyAPI),
        )
        addNewStrategyDialog.destroy()

    # New Manage
    def addViewInNewManage(self):
        frame = Frame(self.tabNewManageFrame)
        self.accountTable = ttk.Treeview(
            frame, selectmode="browse", height=30)
        self.accountTable["columns"] = (
            "Account Name",
            "Amount",
            "Max Strategy",
            "Account Id",
            "Name",
            "Email",
            "Signal",
            "Fraction",
        )
        self.accountTable.column("#0", anchor=CENTER, width=40, minwidth=40)
        self.accountTable.column("Account Name", anchor=CENTER, width=100)
        self.accountTable.column("Amount", anchor=CENTER, width=80)
        self.accountTable.column("Max Strategy", anchor=CENTER, width=80)
        self.accountTable.column("Account Id", anchor=CENTER, width=60)
        self.accountTable.column("Name", anchor=CENTER, width=100)
        self.accountTable.column("Email", anchor=CENTER, width=100)
        self.accountTable.column("Signal", anchor=CENTER, width=80)
        self.accountTable.column("Fraction", anchor=CENTER, width=80)

        self.accountTable.heading("#0", text="ID", anchor=CENTER)
        self.accountTable.heading("Account Name", text="Account Name", anchor=CENTER)
        self.accountTable.heading("Amount", text="Amount", anchor=CENTER)
        self.accountTable.heading(
            "Max Strategy", text="Max Strategy", anchor=CENTER)
        self.accountTable.heading(
            "Account Id", text="Account Id", anchor=CENTER)
        self.accountTable.heading(
            "Name", text="Name", anchor=CENTER)
        self.accountTable.heading(
            "Email", text="Email", anchor=CENTER)
        self.accountTable.heading("Signal", text="Signal", anchor=CENTER)
        self.accountTable.heading("Fraction", text="Fraction", anchor=CENTER)

        yscrollbar = ttk.Scrollbar(
            frame, orient="vertical", command=self.accountTable.yview
        )
        yscrollbar.pack(side=RIGHT, fill=Y)
        self.accountTable.configure(yscrollcommand=yscrollbar.set)

        self.accountNames = []
        self.accountIds={}
        self.accountInfos = {}
        cbDB = self.dbClient[self.SymbolDBName]
        accountList = cbDB["New Manage"].find()
        if accountList != None:
            iid = 0
            for item in accountList:
                self.accountTable.insert(
                    parent="",
                    index="end",
                    iid=iid,
                    text=f"{iid+1}",
                    values=(
                        item["Account Name"],
                        item["Amount"],
                        item["Max Strategy"],
                        item["Account Id"],
                        item["Name"],
                        item["Email"],
                        item["Signal"],
                        item["Fraction"],
                    ),
                )
                self.accountNames.append(item["Account Name"])
                self.accountInfos[item["Account Name"]] = item
                self.accountIds[item["Account Id"]] = item["Account Id"]
                iid+=1

        self.accountTable.pack(side=LEFT, fill=X)
        frame.grid(row=0, column=0, rowspan=100,
                   columnspan=9, padx=10, pady=10)
    
        #New Manage Buttons
    
    def addButtonsInNewManage(self):
        addNewAccountBtn = Button(
            self.tabNewManageFrame,
            text="New Account",
            width=12,
            command=self.onClickAddNewAccount,
        )
        addNewAccountBtn.grid(row=0, column=9, padx=2, pady=2, columnspan=2)
        editAccountBtn = Button(
            self.tabNewManageFrame,
            text="Edit Account",
            width=12,
            command=self.onClickEditAccountBtn,
        )
        editAccountBtn.grid(row=1, column=9, padx=2, columnspan=2)
        removeAccountBtn = Button(
            self.tabNewManageFrame,
            text="Delete",
            width=12,
            command=self.onClickDeleteAccountBtn,
        )
        removeAccountBtn.grid(row=2, column=9, padx=5, columnspan=2)

    def onClickAddNewAccount(self):
        self.showDialogToAddNewAccount()

    def onClickEditAccountBtn(self):
        selectedIndex = self.accountTable.focus()
        if selectedIndex == "":
            messagebox.showerror(title=None, message="Please Select One")
            return
        selectedData = self.accountTable.item(selectedIndex, 'values')
        accountName = selectedData[0]
        print(selectedData)
        self.showDialogToEditAccount(selectedData)

    def onClickDeleteAccountBtn(self):
        selectedItem = self.strategyTable.focus()

    def showDialogToAddNewAccount(self):
        global addAccountDialog
        addAccountDialog = Toplevel()
        addAccountDialog.title("Add New Account")
        # addNewStrategyDialog.grab_set()
        window_width = 320
        window_height = 360
        addAccountDialog.geometry(
            "%dx%d+%d+%d"
            % (
                window_width,
                window_height,
                self.screen_width / 2 - window_width / 2,
                self.screen_height / 2 - window_height / 2,
            )
        )

        accountNameLabel = Label(
            addAccountDialog, text="Account Name")
        accountNameLabel.grid(row=0, column=0, padx=10, pady=5)
        accountNameEntry = Entry(addAccountDialog, width=30)
        accountNameEntry.grid(row=0, column=1, pady=5)
        amountLabel = Label(addAccountDialog,
                                 text="Start Amount")
        amountLabel.grid(row=1, column=0, padx=10, pady=5)
        amountEntry = Entry(addAccountDialog, width=30)
        amountEntry.grid(row=1, column=1, pady=5)
        
        maxStrategyLabel = Label(addAccountDialog,
                                 text="Max Strategy")
        maxStrategyLabel.grid(row=2, column=0, padx=10, pady=5)
        maxStrategyEntry = Entry(addAccountDialog, width=30)
        maxStrategyEntry.grid(row=2, column=1, pady=5)

        accountIdLabel = Label(addAccountDialog,
                                 text="Account Id")
        accountIdLabel.grid(row=3, column=0, padx=10, pady=5)
        accountIdEntry = Entry(addAccountDialog, width=30)
        accountIdEntry.grid(row=3, column=1, pady=5)

        userNameLabel = Label(addAccountDialog,
                                 text="User Name")
        userNameLabel.grid(row=4, column=0, padx=10, pady=5)
        userNameEntry = Entry(addAccountDialog, width=30)
        userNameEntry.grid(row=4, column=1, pady=5)
        userEmailLabel = Label(addAccountDialog,
                                 text="Email")
        userEmailLabel.grid(row=5, column=0, padx=10, pady=5)
        userEmailEntry = Entry(addAccountDialog, width=30)
        userEmailEntry.grid(row=5, column=1, pady=5)
        userSignalLabel = Label(addAccountDialog,
                                 text="Signal")
        userSignalLabel.grid(row=6, column=0, padx=10, pady=5)
        userSignalEntry = Entry(addAccountDialog, width=30)
        userSignalEntry.grid(row=6, column=1, pady=5)

        fractionLabel = Label(addAccountDialog,
                                 text="Fraction")
        fractionLabel.grid(row=7, column=0, padx=10, pady=5)
        fractionEntry = Entry(addAccountDialog, width=30)
        fractionEntry.grid(row=7, column=1, pady=5)

        btnYes = Button(
            addAccountDialog,
            text="  Add  ",
            command=lambda: self.addNewAccountInfo(
                [ 
                    accountNameEntry.get(),
                    amountEntry.get(),
                    maxStrategyEntry.get(),
                    accountIdEntry.get(),
                    userNameEntry.get(),
                    userEmailEntry.get(),
                    userSignalEntry.get(),
                    fractionEntry.get()
                ]
            ),
        )
        btnYes.grid(row=10, column=0, columnspan=2, padx=20, pady=5)
        btnNo = Button(
            addAccountDialog,
            text="  Cancel  ",
            command=lambda: addAccountDialog.destroy(),
        )
        btnNo.grid(row=10, column=1, columnspan=2, padx=20, pady=5)

    def showDialogToEditAccount(self, accountInfo):
        global editAccountDialog
        editAccountDialog = Toplevel()
        editAccountDialog.title("Edit Account")
        # addNewStrategyDialog.grab_set()
        window_width = 320
        window_height = 360
        editAccountDialog.geometry(
            "%dx%d+%d+%d"
            % (
                window_width,
                window_height,
                self.screen_width / 2 - window_width / 2,
                self.screen_height / 2 - window_height / 2,
            )
        )

        accountNameLabel = Label(
            editAccountDialog, text="Account Name")
        accountNameLabel.grid(row=0, column=0, padx=10, pady=5)
        accountNameEntry = Entry(editAccountDialog, width=30)
        accountNameEntry.grid(row=0, column=1, pady=5)
        accountNameEntry.insert(0, accountInfo[0])
        accountNameEntry.config(state=DISABLED)
        amountLabel = Label(editAccountDialog,
                                 text="Start Amount")
        amountLabel.grid(row=1, column=0, padx=10, pady=5)
        amountEntry = Entry(editAccountDialog, width=30)
        amountEntry.grid(row=1, column=1, pady=5)
        amountEntry.insert(0, accountInfo[1])
        
        maxStrategyLabel = Label(editAccountDialog,
                                 text="Max Strategy")
        maxStrategyLabel.grid(row=2, column=0, padx=10, pady=5)
        maxStrategyEntry = Entry(editAccountDialog, width=30)
        maxStrategyEntry.grid(row=2, column=1, pady=5)
        maxStrategyEntry.insert(0, accountInfo[2])

        accountIdLabel = Label(editAccountDialog,
                                 text="Account Id")
        accountIdLabel.grid(row=3, column=0, padx=10, pady=5)
        accountIdEntry = Entry(editAccountDialog, width=30)
        accountIdEntry.grid(row=3, column=1, pady=5)
        accountIdEntry.insert(0, accountInfo[3])
        
        userNameLabel = Label(editAccountDialog,
                                 text="User Name")
        userNameLabel.grid(row=4, column=0, padx=10, pady=5)
        userNameEntry = Entry(editAccountDialog, width=30)
        userNameEntry.grid(row=4, column=1, pady=5)
        userNameEntry.insert(0, accountInfo[4])
        userEmailLabel = Label(editAccountDialog,
                                 text="Email")
        userEmailLabel.grid(row=5, column=0, padx=10, pady=5)
        userEmailEntry = Entry(editAccountDialog, width=30)
        userEmailEntry.grid(row=5, column=1, pady=5)
        userEmailEntry.insert(0, accountInfo[5])
        userSignalLabel = Label(editAccountDialog,
                                 text="Signal")
        userSignalLabel.grid(row=6, column=0, padx=10, pady=5)
        userSignalEntry = Entry(editAccountDialog, width=30)
        userSignalEntry.grid(row=6, column=1, pady=5)
        userSignalEntry.insert(0, accountInfo[6])
        fractionLabel = Label(editAccountDialog,
                                 text="Fraction")
        fractionLabel.grid(row=7, column=0, padx=10, pady=5)
        fractionEntry = Entry(editAccountDialog, width=30)
        fractionEntry.grid(row=7, column=1, pady=5)
        fractionEntry.insert(0, accountInfo[7])

        btnSave = Button(
            editAccountDialog,
            text="  Save  ",
            command=lambda: self.editAccountInfo(
                [ 
                    accountNameEntry.get(),
                    amountEntry.get(),
                    maxStrategyEntry.get(),
                    accountIdEntry.get(),
                    userNameEntry.get(),
                    userEmailEntry.get(),
                    userSignalEntry.get(),
                    fractionEntry.get(),
                ]
            ),
        )
        btnSave.grid(row=10, column=0, columnspan=2, padx=20, pady=5)
        btnNo = Button(
            editAccountDialog,
            text="  Cancel  ",
            command=lambda: editAccountDialog.destroy(),
        )
        btnNo.grid(row=10, column=1, columnspan=2, padx=20, pady=5)

    def addNewAccountInfo(self, accountInfo):
        if accountInfo[0] == "": # account name
            messagebox.showerror(
                title=None, message="Please Enter Account Name")
            return
        if accountInfo[1] == "":
            messagebox.showerror(
                title=None, message="Please Enter Start Amount")
            return
        if accountInfo[0] in self.accountNames:
            messagebox.showerror(
                title=None, message="This Account Name exists already")
            return
        if accountInfo[2] == "":
            messagebox.showerror(
                title=None, message="Please Enter Max Strategy")
            return
        if accountInfo[3] == "":
            messagebox.showerror(
                title=None, message="Please Enter Account Id")
            return
        if accountInfo[4] == "":
            messagebox.showerror(
                title=None, message="Please Enter User Name")
            return
        if accountInfo[5] == "":
            messagebox.showerror(
                title=None, message="Please Enter Email")
            return
        if accountInfo[6] == "":
            messagebox.showerror(
                title=None, message="Please Enter Signal")
            return
        if accountInfo[7] == "":
            messagebox.showerror(
                title=None, message="Please Enter Fraction")
            return
        currentDate = datetime.fromtimestamp(
            datetime.now().timestamp(), tz=self.utc_timezone
        )
        currentDateStr = currentDate.strftime("%Y-%m-%d %H:%M")
        tdDB = self.dbClient[self.SymbolDBName]

        newAccount = {
            "Account Name": accountInfo[0],
            "Amount": accountInfo[1],
            "Max Strategy": accountInfo[2],
            "Account Id": accountInfo[3],
            "Name": accountInfo[4],
            "Email": accountInfo[5],
            "Signal": accountInfo[6],
            "Fraction": accountInfo[7],
            "Created At": currentDateStr,
        }
        collection = tdDB["New Manage"]
        collection.insert_one(newAccount)
        self.accountNames.append(accountInfo[0])
        self.accountIdComboBoxInLive["values"] = self.accountNames
        iid = len(self.accountTable.get_children())
        self.accountTable.insert(
            parent="",
            index="end",
            iid=iid,
            text=f"{iid+1}",
            values=(
                accountInfo[0],
                accountInfo[1],
                accountInfo[2],
                accountInfo[3],
                accountInfo[4],
                accountInfo[5],
                accountInfo[6],
                accountInfo[7],
            ),
        )
        addAccountDialog.destroy()

    def editAccountInfo(self, accountInfo):
        if accountInfo[0] == "": # account name
            messagebox.showerror(
                title=None, message="Please Enter Account Name")
            return
        if accountInfo[1] == "":
            messagebox.showerror(
                title=None, message="Please Enter Start Amount")
            return
        if accountInfo[2] == "":
            messagebox.showerror(
                title=None, message="Please Enter Max Strategy")
            return
        if accountInfo[3] == "":
            messagebox.showerror(
                title=None, message="Please Enter Account Id")
            return
        if accountInfo[4] == "":
            messagebox.showerror(
                title=None, message="Please Enter User Name")
            return
        if accountInfo[5] == "":
            messagebox.showerror(
                title=None, message="Please Enter Email")
            return
        if accountInfo[6] == "":
            messagebox.showerror(
                title=None, message="Please Enter Signal")
            return
        if accountInfo[7] == "":
            messagebox.showerror(
                title=None, message="Please Enter Fraction")
            return

        currentDate = datetime.fromtimestamp(
            datetime.now().timestamp(), tz=self.utc_timezone
        )
        currentDateStr = currentDate.strftime("%Y-%m-%d %H:%M")
        newAccount = {
            "Account Name": accountInfo[0],
            "Amount": accountInfo[1],
            "Max Strategy": accountInfo[2],
            "Account Id": accountInfo[3],
            "Name": accountInfo[4],
            "Email": accountInfo[5],
            "Signal": accountInfo[6],
            "Fraction": accountInfo[7],
            "Created At": currentDateStr,
        }
        tdDB = self.dbClient[self.SymbolDBName]
        collection = tdDB["New Manage"]
        query = {"Account Name": accountInfo[0]}
        newvalues = {"$set": newAccount}
        collection.update_one(query, newvalues)
        self.accountTable.delete(
            *self.accountTable.get_children())
        accountList = collection.find()
        if accountList != None:
            iid = 0
            for item in accountList:
                self.accountTable.insert(
                    parent="",
                    index="end",
                    iid=iid,
                    text=f"{iid+1}",
                    values=(
                        item["Account Name"],
                        item["Amount"],
                        item["Max Strategy"],
                        item["Account Id"],
                        item["Name"],
                        item["Email"],
                        item["Signal"],
                        item["Fraction"],
                    ),
                )
                iid+=1
        editAccountDialog.destroy()

    # Backtest
    def calculateOneTradePrice(self, totalProfit, selectedAccountIndex, position, fraction):
        return (0.99*((totalProfit+float(self.accountInfos[selectedAccountIndex]["Amount"]))*(float(fraction)/100))/(float(self.accountInfos[selectedAccountIndex]["Max Strategy"])*position))
    def sortKey(self, item):
        itemType = self.sortByComboBoxInLive.current()
        if itemType != 0:
            if item[itemType] == "":
                return 0
            else:
                return float(item[itemType])
        else:
            return item[itemType]

    def checkOrderTime(self, strategyName):
        todayDateTime = datetime.now(
            self.newyork_timezone)  # USA/NewYork TimeZone
        self.year = todayDateTime.year
        self.month = todayDateTime.month
        self.date = todayDateTime.day
        weekDay = todayDateTime.weekday()
        oClock = todayDateTime.hour
        minute = todayDateTime.minute
        print(str(oClock)+":"+str(minute), strategyName)
        # if weekDay == 6 or weekDay == 5:
        #     return -1  # Not working day
        if oClock == 15 and (minute >= 46 and minute < 50):
            return 3  # make buy order and check old orders
        if oClock == 16 and (minute >= 15 and minute < 30):
            return 4  # make sell order
        return 0

    def makeProcessOrder(self, none, strategyName, strategyAPI):
        strategyParam = self.startegyParametersList[strategyName]
        selectedAccountName = strategyParam["accountName"]
        accountId = self.accountInfos[selectedAccountName]["Account Id"]
        greeting = self.accountInfos[selectedAccountName]["Name"]
        toEmail = self.accountInfos[selectedAccountName]["Email"]
        toSignalUrl = self.accountInfos[selectedAccountName]["Signal"]
        fraction = self.accountInfos[selectedAccountName]["Fraction"]
        self.runningStateLable.config(text='Running now', fg="#f00")
        count = 1
        self.logInfo(strategyName+" started.")

        while self.threadStateList[strategyName] == True:
            time.sleep(20)
            checkedTime = self.checkOrderTime(strategyName)
            if checkedTime == -1 or checkedTime == 0:  # rest days or not time yet
                count += 1
                count = count % 8
                if count != 0:
                    continue
            # check old orders make buy order and
            if count == 0 or checkedTime == 3:
                currentTimestamp = datetime.now().timestamp()
                tdOrderStateList3pm = None
                if checkedTime == 3:
                    currentTimestamp = datetime.now().timestamp()
                    currentDate = datetime.fromtimestamp(
                        int(currentTimestamp-self.enterDate*24*3600), tz=self.newyork_timezone
                    )
                    enterFromDate = currentDate.strftime("%Y-%m-%d")
                    currentDate = datetime.fromtimestamp(
                        int(currentTimestamp+24*3600), tz=self.newyork_timezone
                    )
                    enterToDate = currentDate.strftime("%Y-%m-%d")

                    while True:
                        currentTimeStamp = datetime.now().timestamp()
                        if (currentTimeStamp - self.lastAPICallTime) >= self.requestInterval:
                            self.lastAPICallTime = currentTimeStamp
                            try:
                                tdOrderStateList3pm = self.tdInstance.get_orders_query(
                                    account=accountId, to_entered_time=enterToDate, from_entered_time=enterFromDate)  # get all order list from TD
                                print("get TD history of account ID: ",
                                      accountId, strategyName)
                                self.logInfo(
                                    "Get TD history of account ID: " + accountId + " " + strategyName)
                            except Exception as e:
                                print(e)
                                # send email
                                body = 'Hi '+greeting+', Getting TD history has failed for account ID = ' +\
                                    accountId+'. ' + str(e)
                                self.logError(body)
                                message = MIMEMultipart()
                                message['From'] = self.sent_from
                                message['To'] = toEmail
                                message['Subject'] = 'TD API Failed'
                                # save this issue in mongodb
                                content = {
                                    'subject': message['Subject'],
                                    'content': body,
                                    'created_at':  datetime.today().strftime('%Y-%m-%d-%H:%M:%S')
                                }
                                stockDB = self.dbClient[self.SymbolDBName]
                                issueCollection = stockDB["Email"]
                                issueCollection.insert_one(
                                    content)
                                # The body and the attachments for the mail
                                message.attach(
                                    MIMEText(body, 'plain'))
                                try:
                                    requests.get(
                                        toSignalUrl+body.replace("#", ""))
                                except Exception as ex:
                                    print("Signal went error", ex)
                                    self.logError(
                                        "TD order history error Signal went error "+str(ex))
                                try:
                                    smtp_server = smtplib.SMTP_SSL(
                                        'smtp.gmail.com', 465)
                                    smtp_server.ehlo()
                                    smtp_server.login(
                                        self.gmail_user, self.gmail_password)
                                    email_text = message.as_string()
                                    smtp_server.sendmail(
                                        self.sent_from, toEmail, email_text)
                                    smtp_server.close()
                                    print(
                                        "Email sent successfully!")
                                    self.logInfo(
                                        " TD order history error Email sent successfully!")
                                except Exception as ex:
                                    print(
                                        "Email sending failed", ex)
                                    self.logError(
                                        "TD order history error Email sending failed "+str(ex))
                            break
                        time.sleep(self.requestCheckInterval)

                else:
                    try:
                        tdOrderStateList3pm = self.tdOrderStateList[accountId]
                    except KeyError:
                        print("TD order is empty for account id "+accountId)
                        self.logInfo(
                            "TD order is empty for account id "+accountId)

                query = {"strategyName": strategyName, "instruction": {"$in": ["SELL", "BUY_TO_COVER"]}, "state": {
                    "$nin": ["FILLED", "CANCELED", "REJECTED"]}, "timestamp": {"$gte": int(currentTimestamp-self.enterDate*24*3600)}}
                # get orders from DB with query
                stockDB = self.dbClient[self.SymbolDBName]
                collection = stockDB["OrderList"]
                validOrderListFromDB = collection.find(query).sort(
                    "timestamp", pymongo.ASCENDING)

                # check and update with db and td
                if validOrderListFromDB != None and tdOrderStateList3pm != None:
                    if checkedTime == 3:
                        # get exit conditions
                        strategyParam = self.startegyParametersList[strategyName]
                        exitAPIResponse = None
                        if strategyParam["isExitAPI"] == 1 and strategyParam["exitAPI"] != "":
                            try:
                                exitAPIResponse = requests.get(
                                    strategyParam["exitAPI"], timeout=8)
                            except requests.exceptions.Timeout as e:
                                print("Time Out in ExitAPI of " + strategyName)
                                self.logError(
                                    "Time Out in ExitAPI of " + strategyName)
                                content = {
                                    "subject": strategyName + ": CheckTime_1 Exit API request error",
                                    "content": str(e),
                                    "created_at": datetime.today().strftime(
                                        "%Y-%m-%d-%H:%M:%S"
                                    )
                                }
                                binanceBD = self.dbClient[self.SymbolDBName]
                                errorCollection = binanceBD["Error"]
                                errorCollection.insert_one(content)
                            except requests.exceptions.HTTPError as e:
                                print("HTTPError in ExitAPI of " + strategyName)
                                self.logError(
                                    "HTTPError in ExitAPI of " + strategyName)
                                content = {
                                    "subject": strategyName + ": CheckTime_1 Exit API request error",
                                    "content": str(e),
                                    "created_at": datetime.today().strftime(
                                        "%Y-%m-%d-%H:%M:%S"
                                    )
                                }
                                binanceBD = self.dbClient[self.SymbolDBName]
                                errorCollection = binanceBD["Error"]
                                errorCollection.insert_one(content)
                            except requests.exceptions.RequestException as e:
                                print(
                                    "RequestException in ExitAPI of " + strategyName)
                                self.logError(
                                    "RequestException in ExitAPI of " + strategyName)
                                content = {
                                    "subject": strategyName + ": CheckTime_1 Exit API request error",
                                    "content": str(e),
                                    "created_at": datetime.today().strftime(
                                        "%Y-%m-%d-%H:%M:%S"
                                    )
                                }
                                binanceBD = self.dbClient[self.SymbolDBName]
                                errorCollection = binanceBD["Error"]
                                errorCollection.insert_one(content)
                            except requests.exceptions.TooManyRedirects as e:
                                print(
                                    "TooManyRedirects in ExitAPI of " + strategyName)
                                self.logError(
                                    "TooManyRedirects in ExitAPI of " + strategyName)
                                content = {
                                    "subject": strategyName + ": CheckTime_1 Exit API request error",
                                    "content": str(e),
                                    "created_at": datetime.today().strftime(
                                        "%Y-%m-%d-%H:%M:%S"
                                    )
                                }
                                binanceBD = self.dbClient[self.SymbolDBName]
                                errorCollection = binanceBD["Error"]
                                errorCollection.insert_one(content)
                        symbolsToExit = []
                        if exitAPIResponse != None:
                            for data in exitAPIResponse.text.splitlines():
                                item = data.split("|")
                                symbolsToExit.append(item[0])
                            exitAPIResponse.close()

                    for mongoItem in validOrderListFromDB:
                        for tdOrderItem in tdOrderStateList3pm:
                            if tdOrderItem["orderId"] == int(mongoItem["order_id"]):
                                newValues = {
                                    "$set": {"state": tdOrderItem["status"], "timestamp": datetime.now().timestamp()}
                                }
                                collection = stockDB["OrderList"]
                                collection.update_one(
                                    {"order_id": str(tdOrderItem["orderId"])}, newValues)
                                # sell order
                                if tdOrderItem["orderLegCollection"][0]["instruction"] == "SELL" or tdOrderItem["orderLegCollection"][0]["instruction"] == "BUY_TO_COVER":
                                    # only GTC sell order working yet then
                                    if checkedTime == 3 and (tdOrderItem["status"] == "WORKING" or tdOrderItem["status"] == "QUEUED" or tdOrderItem["status"] == "ACCEPTED" or tdOrderItem["status"] == "PENDING_ACTIVATION") and mongoItem["duration"] == "GOOD_TILL_CANCEL":
                                        exitCondition = False
                                        exitReason = ""
                                        # check the exit condition
                                        if strategyParam["isDayExit"] == 1 and strategyParam["dayExit"] != "" and len(strategyParam["dayExit"]) > 0:
                                            f_date = date(
                                                int(mongoItem["year"]), mongoItem["month"], mongoItem["date"])
                                            l_date = date(
                                                self.year, self.month, self.date)
                                            delta = l_date - f_date
                                            if delta.days >= int(strategyParam["dayExit"]):
                                                exitCondition = True
                                                exitReason += "Exit Day"
                                        if mongoItem["symbol"] in symbolsToExit:
                                            exitCondition = True
                                            exitReason += " Exit API"
                                        if exitCondition == True:
                                            # cancel sell order and make new order
                                            cancelResult = None

                                            while True:
                                                currentTimeStamp = datetime.now().timestamp()
                                                if (currentTimeStamp - self.lastAPICallTime) >= self.requestInterval:
                                                    self.lastAPICallTime = currentTimeStamp
                                                    try:
                                                        cancelResult = self.tdInstance.cancel_order(
                                                            account=accountId, order_id=tdOrderItem["orderId"])
                                                        print(
                                                            "Cancel First Sell Order", tdOrderItem["orderId"], mongoItem["symbol"], strategyName)
                                                        self.logInfo("Cancel First Sell Order " + str(
                                                            tdOrderItem["orderId"])+" " + mongoItem["symbol"]+" "+strategyName)
                                                    except Exception as e:
                                                        print(
                                                            "Cancel First Sell Order has error ", tdOrderItem["orderId"], mongoItem["symbol"], strategyName)
                                                        self.logInfo("Cancel First Sell Order  has error " + str(
                                                            tdOrderItem["orderId"])+" " + mongoItem["symbol"]+" "+strategyName + " "+str(e))
                                                    break
                                                time.sleep(
                                                    self.requestCheckInterval)

                                            if cancelResult != None:
                                                # update sell order state
                                                newValues = {
                                                    "$set": {"state": "CANCELED", "actualExit": exitReason, "timestamp": datetime.now().timestamp()}}
                                                collection = stockDB["OrderList"]
                                                collection.update_one(
                                                    {"order_id": str(tdOrderItem["orderId"])}, newValues)
                                                # make second sell
                                                secondSellOrder = Order()
                                                secondSellOrder.order_session(
                                                    session=ORDER_SESSION.NORMAL)
                                                secondSellOrder.order_type(
                                                    order_type=ORDER_TYPE.MARKET)
                                                secondSellOrder.order_duration(
                                                    duration=DURATION.DAY)
                                                secondSellOrder.order_strategy_type(
                                                    order_strategy_type=ORDER_STRATEGY_TYPE.SINGLE)
                                                secondSellOrderLeg = OrderLeg()
                                                if mongoItem["type"] == 0:
                                                    secondSellOrderLeg.order_leg_instruction(
                                                        instruction=ORDER_INSTRUCTIONS.SELL)
                                                else:
                                                    secondSellOrderLeg.order_leg_instruction(
                                                        instruction=ORDER_INSTRUCTIONS.BUY_TO_COVER)
                                                secondSellOrderLeg.order_leg_asset(
                                                    asset_type=ORDER_ASSET_TYPE.EQUITY, symbol=mongoItem["symbol"])
                                                secondSellOrderLeg.order_leg_quantity(
                                                    quantity=mongoItem["quantity"])
                                                secondSellOrder.add_order_leg(
                                                    order_leg=secondSellOrderLeg)

                                                while True:
                                                    currentTimeStamp = datetime.now().timestamp()
                                                    if (currentTimeStamp - self.lastAPICallTime) >= self.requestInterval:
                                                        self.lastAPICallTime = currentTimeStamp
                                                        try:
                                                            result = self.tdInstance.place_order(
                                                                order=secondSellOrder, account=accountId)
                                                            request = json.loads(
                                                                result["request_body"])
                                                            print(
                                                                "Make Second Sell Order by Exit", result["order_id"], mongoItem["symbol"], strategyName)
                                                            self.logInfo("Make Second Sell Order by Exit " + str(
                                                                result["order_id"])+" "+mongoItem["symbol"]+" "+strategyName)
                                                            secondSellOrderInfo = {
                                                                "strategyName": strategyName,
                                                                "account_id": accountId,
                                                                "order_id": result["order_id"],
                                                                "Date": result["headers"]["Date"],
                                                                "orderType": request["orderType"],
                                                                "orderStrategyType": request["orderStrategyType"],
                                                                "duration": request["duration"],
                                                                "profit": 0,
                                                                "price": 0,
                                                                # buy or sell
                                                                "instruction": request["orderLegCollection"][0]["instruction"],
                                                                "symbol": request["orderLegCollection"][0]["instrument"]["symbol"],
                                                                "quantity": request["orderLegCollection"][0]["quantity"],
                                                                "orderLegCollection": request["orderLegCollection"],
                                                                "boughtPrice": mongoItem["boughtPrice"],
                                                                "parentOrderId": mongoItem["order_id"],
                                                                "actualExit": exitReason,
                                                                "year": self.year,
                                                                "month": self.month,
                                                                "date": self.date,
                                                                "type": mongoItem["type"],
                                                                "state": "None",
                                                                "timestamp": datetime.now().timestamp()
                                                            }
                                                            # stockDB = self.dbClient[self.SymbolDBName]
                                                            collection = stockDB["OrderList"]
                                                            collection.insert_one(
                                                                secondSellOrderInfo)
                                                        except Exception as e:
                                                            print(e)
                                                            # send email
                                                            body = 'Hi '+greeting+', Making Second Sell Order has failed for strategy `'+strategyName+'` for stock `' + \
                                                                mongoItem["symbol"] + \
                                                                '`. account Id = ' + \
                                                                accountId + \
                                                                '. ' + str(e)
                                                            self.logError(body)
                                                            message = MIMEMultipart()
                                                            message['From'] = self.sent_from
                                                            message['To'] = toEmail
                                                            message['Subject'] = 'Making Second Sell Order Failed'
                                                            # save this issue in mongodb
                                                            content = {
                                                                'subject': message['Subject'],
                                                                'content': body,
                                                                'created_at':  datetime.today().strftime('%Y-%m-%d-%H:%M:%S')
                                                            }
                                                            issueCollection = stockDB["Email"]
                                                            issueCollection.insert_one(
                                                                content)
                                                            # The body and the attachments for the mail
                                                            message.attach(
                                                                MIMEText(body, 'plain'))

                                                            try:
                                                                requests.get(
                                                                    toSignalUrl+body.replace("#", ""))
                                                            except Exception as ex:
                                                                print(
                                                                    "Signal went error", ex)
                                                                self.logError(
                                                                    "Signal went error " + str(ex) + " "+strategyName)
                                                            try:
                                                                smtp_server = smtplib.SMTP_SSL(
                                                                    'smtp.gmail.com', 465)
                                                                smtp_server.ehlo()
                                                                smtp_server.login(
                                                                    self.gmail_user, self.gmail_password)
                                                                email_text = message.as_string()
                                                                smtp_server.sendmail(
                                                                    self.sent_from, toEmail, email_text)
                                                                smtp_server.close()
                                                                print(
                                                                    "Email sent successfully!")
                                                                self.logInfo(
                                                                    "Email sent successfully! "+strategyName)
                                                            except Exception as ex:
                                                                print(
                                                                    "send email error", ex)
                                                                self.logError(
                                                                    "send email error" + str(ex) + " "+strategyName)
                                                        break
                                                    time.sleep(
                                                        self.requestCheckInterval)
                                    # sell order failed
                                    elif tdOrderItem["status"] != "FILLED":
                                        # sell order failed
                                        if tdOrderItem["status"] != "WORKING" and tdOrderItem["status"] != "QUEUED" and tdOrderItem["status"] != "ACCEPTED" and tdOrderItem["status"] != "PENDING_ACTIVATION":
                                            if mongoItem["orderType"] == "MARKET_ON_CLOSE":
                                                failedSecondOrderInfo = {
                                                    "strategyName": strategyName,
                                                    "account_id": accountId,
                                                    "order_id": tdOrderItem["orderId"],
                                                    "orderType": mongoItem["orderType"],
                                                    "instruction": mongoItem["instruction"],
                                                    "symbol": mongoItem["symbol"],
                                                    "quantity": mongoItem["quantity"],
                                                    "year": self.year,
                                                    "month": self.month,
                                                    "date": self.date,
                                                    "state": tdOrderItem["status"],
                                                    "timestamp": datetime.now().timestamp()
                                                }
                                                failedSellOrderCollection = stockDB["FailedSellOrderList"]
                                                failedSellOrderCollection.insert_one(
                                                    failedSecondOrderInfo)
                                                print("Second Sell Order "+tdOrderItem["status"],
                                                      mongoItem["order_id"])
                                                self.logInfo(
                                                    "Second Sell Order status is " + tdOrderItem["status"] + " "+strategyName+" " + str(mongoItem["order_id"]))
                                                # send email
                                                body = 'Hi '+greeting+', Order #' + \
                                                    mongoItem["order_id"]+' for strategy `'+strategyName+'` for stock `' + \
                                                    mongoItem["symbol"] + \
                                                    '` has failed to trigger a sell order. Please check. account Id = '+accountId+'.'
                                                self.logInfo(body)
                                                message = MIMEMultipart()
                                                message['From'] = self.sent_from
                                                message['To'] = toEmail
                                                message['Subject'] = 'Second Sell Order Rejected Or Canceled'
                                                # save this issue in mongodb
                                                content = {
                                                    'subject': message['Subject'],
                                                    'content': body,
                                                    'created_at':  datetime.today().strftime('%Y-%m-%d-%H:%M:%S')
                                                }
                                                issueCollection = stockDB["Email"]
                                                issueCollection.insert_one(
                                                    content)
                                                # The body and the attachments for the mail
                                                message.attach(
                                                    MIMEText(body, 'plain'))

                                                try:
                                                    requests.get(
                                                        toSignalUrl+body.replace("#", ""))
                                                except Exception as ex:
                                                    self.logError(
                                                        "Signal went error " + str(ex) + " "+strategyName)
                                                try:
                                                    smtp_server = smtplib.SMTP_SSL(
                                                        'smtp.gmail.com', 465)
                                                    smtp_server.ehlo()
                                                    smtp_server.login(
                                                        self.gmail_user, self.gmail_password)
                                                    email_text = message.as_string()
                                                    smtp_server.sendmail(
                                                        self.sent_from, toEmail, email_text)
                                                    smtp_server.close()
                                                    print(
                                                        "Email sent successfully!")
                                                    self.logInfo(
                                                        "Email sent successfully! "+strategyName)
                                                except Exception as ex:
                                                    print(
                                                        "send email error", ex)
                                                    self.logError(
                                                        "send email error" + str(ex) + " "+strategyName)
                                            else:  # first sell order rejected or canceled
                                                # send email
                                                failedFirstOrderInfo = {
                                                    "strategyName": strategyName,
                                                    "account_id": accountId,
                                                    "order_id": tdOrderItem["orderId"],
                                                    "orderType": mongoItem["orderType"],
                                                    "instruction": mongoItem["instruction"],
                                                    "symbol": mongoItem["symbol"],
                                                    "quantity": mongoItem["quantity"],
                                                    "year": self.year,
                                                    "month": self.month,
                                                    "date": self.date,
                                                    "state": tdOrderItem["status"],
                                                    "timestamp": datetime.now().timestamp()
                                                }
                                                failedSellOrderCollection = stockDB["FailedSellOrderList"]
                                                failedSellOrderCollection.insert_one(
                                                    failedFirstOrderInfo)
                                                print("First Sell Order "+tdOrderItem["status"],
                                                      mongoItem["order_id"], strategyName)
                                                self.logInfo(
                                                    "First Sell Order status is " + tdOrderItem["status"] + " "+strategyName+" " + str(mongoItem["order_id"]))
                                                # send email
                                                body = 'Hi '+greeting+', Order #' + \
                                                    mongoItem["order_id"]+' for strategy `'+strategyName+'` for stock `' + \
                                                    mongoItem["symbol"] + \
                                                    '` has failed to trigger a sell order. Please check. account Id = '+accountId+'.'
                                                self.logInfo(body)
                                                message = MIMEMultipart()
                                                message['From'] = self.sent_from
                                                message['To'] = toEmail
                                                message['Subject'] = 'First Sell Order Rejected or Canceled'
                                                # save this issue in mongodb
                                                content = {
                                                    'subject': message['Subject'],
                                                    'content': body,
                                                    'created_at':  datetime.today().strftime('%Y-%m-%d-%H:%M:%S')
                                                }
                                                issueCollection = stockDB["Email"]
                                                issueCollection.insert_one(
                                                    content)
                                                # The body and the attachments for the mail
                                                message.attach(
                                                    MIMEText(body, 'plain'))

                                                try:
                                                    requests.get(
                                                        toSignalUrl+body.replace("#", ""))
                                                except Exception as ex:
                                                    self.logError(
                                                        "Signal went error " + str(ex) + " "+strategyName)
                                                try:
                                                    smtp_server = smtplib.SMTP_SSL(
                                                        'smtp.gmail.com', 465)
                                                    smtp_server.ehlo()
                                                    smtp_server.login(
                                                        self.gmail_user, self.gmail_password)
                                                    email_text = message.as_string()
                                                    smtp_server.sendmail(
                                                        self.sent_from, toEmail, email_text)
                                                    smtp_server.close()
                                                    print(
                                                        "Email sent successfully!")
                                                    self.logInfo(
                                                        "Email sent successfully! "+strategyName)
                                                except Exception as ex:
                                                    print(
                                                        "send email error", ex)
                                                    self.logError(
                                                        "send email error " + str(ex) + " "+strategyName)
                                    elif tdOrderItem["status"] == "FILLED":
                                        # any type sell order successed, sending email
                                        if mongoItem["orderType"] == "LIMIT":
                                            if mongoItem["type"] == 0:  # long case
                                                profit = float(tdOrderItem['price']) * float(tdOrderItem["filledQuantity"]) - float(
                                                    mongoItem["boughtPrice"]) * float(mongoItem["quantity"])
                                            else:
                                                profit = float(
                                                    mongoItem["boughtPrice"]) * float(mongoItem["quantity"]) - float(tdOrderItem['price']) * float(tdOrderItem["filledQuantity"])
                                            actualExit = "Profit%"
                                            if mongoItem["isATR"] == 1:
                                                actualExit = "ATR"
                                            newValues = {
                                                "$set": {
                                                    "profit": profit,
                                                    "filledPrice": tdOrderItem['price'],
                                                    "filledQuantity": tdOrderItem["filledQuantity"],
                                                    "closeTime": tdOrderItem["closeTime"],
                                                    "actualExit": actualExit
                                                }
                                            }
                                            collection = stockDB["OrderList"]
                                            collection.update_one(
                                                {"order_id": str(tdOrderItem["orderId"])}, newValues)
                                        else:
                                            profit = float(tdOrderItem['orderActivityCollection'][0]['executionLegs'][0]['price'])*float(
                                                tdOrderItem["filledQuantity"]) - float(mongoItem["boughtPrice"])*float(mongoItem["quantity"])
                                            newValues = {
                                                "$set": {
                                                    "profit": profit,
                                                    "price": tdOrderItem['orderActivityCollection'][0]['executionLegs'][0]['price'],
                                                    "filledPrice": tdOrderItem['orderActivityCollection'][0]['executionLegs'][0]['price'],
                                                    "filledQuantity": tdOrderItem["filledQuantity"],
                                                    "closeTime": tdOrderItem["closeTime"],
                                                    "actualExit": "Market"
                                                }
                                            }
                                            collection = stockDB["OrderList"]
                                            collection.update_one(
                                                {"order_id": str(tdOrderItem["orderId"])}, newValues)
                                        body = 'Hi '+greeting+', Order #' + \
                                            mongoItem["order_id"]+' for strategy `'+strategyName+'` for stock `' + \
                                            mongoItem["symbol"]+'` has filled. And the profit was USD ' + \
                                            str(profit)+'. Please check. account Id = ' + \
                                            accountId+'.\n'

                                        body = body + \
                                            self.getStrategyProfitInfo(
                                                strategyName)
                                        self.logInfo(body)
                                        message = MIMEMultipart()
                                        message['From'] = self.sent_from
                                        message['To'] = toEmail
                                        message['Subject'] = 'Sell Order Filled'
                                        # save this issue in mongodb
                                        content = {
                                            'subject': message['Subject'],
                                            'content': body,
                                            'created_at':  datetime.today().strftime('%Y-%m-%d-%H:%M:%S')
                                        }
                                        issueCollection = stockDB["Email"]
                                        issueCollection.insert_one(content)

                                        # The body and the attachments for the mail
                                        message.attach(MIMEText(body, 'plain'))

                                        try:
                                            body = body.replace("$", "")
                                            requests.get(
                                                toSignalUrl+body.replace("#", ""))
                                        except Exception as ex:
                                            self.logError(
                                                "Signal went error " + str(ex) + " "+strategyName)
                                        try:
                                            smtp_server = smtplib.SMTP_SSL(
                                                'smtp.gmail.com', 465)
                                            smtp_server.ehlo()
                                            smtp_server.login(
                                                self.gmail_user, self.gmail_password)
                                            email_text = message.as_string()
                                            smtp_server.sendmail(
                                                self.sent_from, toEmail, email_text)
                                            smtp_server.close()
                                            print(
                                                "Email sent successfully!")
                                            self.logInfo(
                                                "Email sent successfully! "+strategyName)
                                        except Exception as ex:
                                            print(
                                                "send email error", ex)
                                            self.logError(
                                                "send email error" + str(ex) + " "+strategyName)

                if checkedTime == 3:
                    # Check old orders state
                    query = {"strategyName": strategyName, "state": {
                        "$nin": ["FILLED", "CANCELED", "REJECTED"]}, "timestamp": {"$gte": int(currentTimestamp-self.enterDate*24*3600)}}
                    collection = stockDB["OrderList"]
                    validOrderListFromDB = collection.find(query).sort(
                        "timestamp", pymongo.DESCENDING)
                    alreadyAliveSymbols = []
                    if validOrderListFromDB != None:
                        for mongoItem in validOrderListFromDB:
                            try:
                                alreadyAliveSymbols.append(mongoItem["symbol"])
                            except:
                                continue
                    # if already using order number is 10, this strategy skips.
                    strategyPosition = self.positionComboBoxInLive.current()+1
                    self.logInfo(strategyName+" existed stocks are " +
                                 str(len(alreadyAliveSymbols)))
                    if len(alreadyAliveSymbols) < strategyPosition:
                        position = strategyPosition - len(alreadyAliveSymbols)
                        # calculate the profit
                        amountSell = 0
                        amountBuy = 0
                        query = {"instruction": "SELL",
                                 "state": "FILLED", "account_id": accountId}
                        collection = stockDB["OrderList"]
                        allSuccessedOrders = collection.find(
                            query).sort("timestamp", pymongo.DESCENDING)
                        for successedOrder in allSuccessedOrders:
                            amountSell += float(successedOrder["filledPrice"])*float(
                                successedOrder["filledQuantity"])
                            amountBuy += float(successedOrder["boughtPrice"])*float(
                                successedOrder["orderLegCollection"][0]["quantity"])
                        totalProfit = amountSell - amountBuy
                        # make new buy order
                        sortOrder = self.sortOrderComboBoxInLive.current()
                        self.currentAPIEntryTable.delete(
                            *self.currentAPIEntryTable.get_children())

                        response = None
                        if strategyAPI != None and strategyAPI != "":
                            try:
                                response = requests.get(strategyAPI, timeout=9)
                            except requests.exceptions.Timeout:
                                print("Time Out in EntryAPI of " + strategyName)
                                self.logError(
                                    "Time Out in EntryAPI of " + strategyName)
                                content = {
                                    "subject": strategyName + ": CheckTime_1 Entry API request error",
                                    "content": str(e),
                                    "created_at": datetime.today().strftime(
                                        "%Y-%m-%d-%H:%M:%S"
                                    )
                                }
                                binanceBD = self.dbClient[self.SymbolDBName]
                                errorCollection = binanceBD["Error"]
                                errorCollection.insert_one(content)
                            except requests.exceptions.HTTPError:
                                print("HTTPError in EntryAPI of " + strategyName)
                                self.logError(
                                    "HTTPError in EntryAPI of " + strategyName)
                                content = {
                                    "subject": strategyName + ": CheckTime_1 Entry API request error",
                                    "content": str(e),
                                    "created_at": datetime.today().strftime(
                                        "%Y-%m-%d-%H:%M:%S"
                                    )
                                }
                                binanceBD = self.dbClient[self.SymbolDBName]
                                errorCollection = binanceBD["Error"]
                                errorCollection.insert_one(content)
                            except requests.exceptions.RequestException as e:
                                print(
                                    "RequestException in EntryAPI of " + strategyName)
                                self.logError(
                                    "RequestException in EntryAPI of " + strategyName)
                                content = {
                                    "subject": strategyName + ": CheckTime_1 Entry API request error",
                                    "content": str(e),
                                    "created_at": datetime.today().strftime(
                                        "%Y-%m-%d-%H:%M:%S"
                                    )
                                }
                                binanceBD = self.dbClient[self.SymbolDBName]
                                errorCollection = binanceBD["Error"]
                                errorCollection.insert_one(content)
                            except requests.exceptions.TooManyRedirects:
                                print(
                                    "TooManyRedirects in EntryAPI of " + strategyName)
                                self.logError(
                                    "TooManyRedirects in EntryAPI of " + strategyName)
                                content = {
                                    "subject": strategyName + ": CheckTime_1 Entry API request error",
                                    "content": str(e),
                                    "created_at": datetime.today().strftime(
                                        "%Y-%m-%d-%H:%M:%S"
                                    )
                                }
                                binanceBD = self.dbClient[self.SymbolDBName]
                                errorCollection = binanceBD["Error"]
                                errorCollection.insert_one(content)
                        fullResult = []
                        result = []
                        symbolNamesForQuotes = []
                        if response != None:
                            utcDateNow = datetime.now(self.utc_timezone)
                            month = utcDateNow.month
                            day = utcDateNow.day
                            if month < 0:
                                month = "0"+str(month)
                            else:
                                month = str(month)
                            if day < 10:
                                day = "0"+str(day)
                            else:
                                day = str(day)
                            currentUTCDateStr = month+"/" + \
                                day+"/"+str(utcDateNow.year)
                            for data in response.text.splitlines():
                                item = data.split("|")
                                fullResult.append(item)
                                #If current date and time is not the current date and time, do not make a trade
                                if len(item[0]) < 6  and item[0] not in alreadyAliveSymbols:
                                    if strategyParam["isATR"] == 1 and item[2].startswith(currentUTCDateStr) and item[3] == "":
                                        continue
                                    result.append(item)
                                    symbolNamesForQuotes.append(item[0])
                            response.close()
                        if len(result) == 0:
                            # messagebox.showinfo(
                            #     title=None, message="There is not any good stock")
                            print("There is not any good stock")
                            self.logInfo(
                                "There is not any stock to make buy order in " + strategyName)
                            continue

                        quotes = None
                        while True:
                            currentTimeStamp = datetime.now().timestamp()
                            if (currentTimeStamp - self.lastAPICallTime) >= self.requestInterval:
                                self.lastAPICallTime = currentTimeStamp
                                try:
                                    quotes = self.tdInstance.get_quotes(
                                        instruments=symbolNamesForQuotes)
                                    print("Get Quotes", strategyName)
                                    self.logInfo(
                                        "Get Quotes in " + strategyName)
                                except Exception as e:
                                    print("Get Quotes Error in "+strategyName)
                                    self.logError(
                                        "Get Quotes Error in "+strategyName)
                                break
                            time.sleep(self.requestCheckInterval)
                        if quotes == None:
                            continue

                        for key, value in quotes.items():
                            if value["totalVolume"] < 10000:
                                index = len(result)
                                while index > 0:
                                    if result[index-1][0] == key:
                                        result.pop(index-1)
                                        self.logInfo(
                                            key + " volume is under 10000 in " + strategyName)
                                        break
                                    index = index-1
                        if(sortOrder == 0):
                            result.sort(key=self.sortKey, reverse=False)
                            fullResult.sort(key=self.sortKey, reverse=False)
                        else:
                            result.sort(key=self.sortKey, reverse=True)
                            fullResult.sort(key=self.sortKey, reverse=True)
                        iid = 0
                        selectedPosition = self.strategyComboBoxInLive.current()
                        if strategyName == self.strategyNamesArray[selectedPosition]:
                            self.currentAPIEntryTable.delete(
                                *self.currentAPIEntryTable.get_children())
                            for item in fullResult:
                                # stock information
                                self.currentAPIEntryTable.insert(
                                    parent="",
                                    index="end",
                                    iid=iid,
                                    text=f"{iid+1}",
                                    values=(
                                        item[0],
                                        item[1],
                                        item[2],
                                        item[3],
                                        item[4],
                                        item[5],
                                        item[6],
                                        item[7],
                                        item[8],
                                        item[9],
                                        item[10],
                                        item[11],
                                        item[12],
                                    ),
                                )
                                iid += 1

                        if len(result) == 0:
                            print("There is not any stock has 10000+ volume")
                            self.logInfo(
                                "There is not any stock has 10000+ volume in " + strategyName)
                            continue
                        for item in result[0:position]:
                            quantity = int(self.calculateOneTradePrice(
                                totalProfit, selectedAccountName, strategyPosition, fraction)/float(item[1]))
                            if quantity <= 0:
                                errorTxt = "Failed to make order for `" + \
                                    item[0] + "` of `"+strategyName + \
                                    "` because quantity is 0."
                                self.logError(errorTxt)
                                print(errorTxt)
                                # send email
                                body = 'Hi '+greeting+', '+errorTxt+' Please check. account Id = '+accountId+'.'
                                message = MIMEMultipart()
                                message['From'] = self.sent_from
                                message['To'] = toEmail
                                message['Subject'] = 'Making Buy Order Failed'
                                # save this issue in mongodb
                                content = {
                                    'subject': message['Subject'],
                                    'content': errorTxt,
                                    'created_at':  datetime.today().strftime('%Y-%m-%d-%H:%M:%S')
                                }
                                issueCollection = stockDB["Email"]
                                issueCollection.insert_one(content)
                                # The body and the attachments for the mail
                                message.attach(
                                    MIMEText(body, 'plain'))

                                try:
                                    requests.get(toSignalUrl +
                                                 body.replace("#", ""))
                                except Exception as ex:
                                    print("Signal went error", ex)
                                    self.logError(
                                        "Signal went error " + str(ex)+" "+strategyName)
                                try:
                                    smtp_server = smtplib.SMTP_SSL(
                                        'smtp.gmail.com', 465)
                                    smtp_server.ehlo()
                                    smtp_server.login(
                                        self.gmail_user, self.gmail_password)
                                    email_text = message.as_string()
                                    smtp_server.sendmail(
                                        self.sent_from, toEmail, email_text)
                                    smtp_server.close()
                                    print(
                                        "Email sent successfully!")
                                    self.logInfo(
                                        "Email sent successfully! "+strategyName)
                                except Exception as ex:
                                    print(
                                        "Email sending failed", ex)
                                    self.logError(
                                        "Email sending failed " + str(ex)+" "+strategyName)
                                continue
                            buyOrder = Order()
                            buyOrder.order_session(
                                session=ORDER_SESSION.NORMAL)
                            buyOrder.order_type(
                                order_type=ORDER_TYPE.MARKET_ON_CLOSE)
                            buyOrder.order_duration(duration=DURATION.DAY)
                            buyOrder.order_strategy_type(
                                order_strategy_type=ORDER_STRATEGY_TYPE.SINGLE)
                            buyOrderLeg = OrderLeg()
                            if strategyParam['instruction'] == 0:
                                buyOrderLeg.order_leg_instruction(
                                    instruction=ORDER_INSTRUCTIONS.BUY)
                            else:
                                buyOrderLeg.order_leg_instruction(
                                    instruction=ORDER_INSTRUCTIONS.SELL_SHORT)
                            buyOrderLeg.order_leg_asset(
                                asset_type=ORDER_ASSET_TYPE.EQUITY, symbol=item[0])
                            buyOrderLeg.order_leg_quantity(quantity=quantity)
                            buyOrder.add_order_leg(order_leg=buyOrderLeg)

                            while True:
                                currentTimeStamp = datetime.now().timestamp()
                                if (currentTimeStamp - self.lastAPICallTime) >= self.requestInterval:
                                    self.lastAPICallTime = currentTimeStamp
                                    try:
                                        result = self.tdInstance.place_order(
                                            order=buyOrder, account=accountId)
                                        request = json.loads(
                                            result["request_body"])
                                        print(
                                            "Make Buy Order", result["order_id"], request["orderLegCollection"][0]["instrument"]["symbol"], strategyName)
                                        self.logInfo("Make Buy Order "+str(
                                            result["order_id"])+" "+request["orderLegCollection"][0]["instrument"]["symbol"]+" "+strategyName)
                                        buyOrderInfo = {
                                            "strategyName": strategyName,
                                            "account_id": accountId,
                                            "order_id": result["order_id"],
                                            "Date": result["headers"]["Date"],
                                            "orderType": request["orderType"],
                                            "orderStrategyType": request["orderStrategyType"],
                                            "duration": request["duration"],
                                            "instruction": request["orderLegCollection"][0]["instruction"],
                                            "symbol": request["orderLegCollection"][0]["instrument"]["symbol"],
                                            "quantity": request["orderLegCollection"][0]["quantity"],
                                            # useless value.
                                            "price": float(item[1]),
                                            "atr": item[3],  # from entry api
                                            "atrValue": strategyParam["atr"],
                                            "profitPercent": strategyParam["profit"],
                                            "isATR": strategyParam["isATR"],
                                            "orderLegCollection": request["orderLegCollection"],
                                            "year": self.year,
                                            "month": self.month,
                                            "date": self.date,
                                            "state": "None",
                                            "type": strategyParam['instruction'],
                                            "timestamp": datetime.now().timestamp()
                                        }
                                        stockDB = self.dbClient[self.SymbolDBName]
                                        collection = stockDB["OrderList"]
                                        collection.insert_one(buyOrderInfo)
                                    except Exception as e:
                                        print(e)
                                        print(
                                            "Failed to make order for "+item[0])
                                        # send email
                                        body = 'Hi '+greeting+', Making order has failed for strategy `'+strategyName+'` for stock `' + \
                                            item[0] + \
                                            '`. account Id = ' + \
                                            accountId+'. ' + str(e)
                                        self.logError(body)
                                        message = MIMEMultipart()
                                        message['From'] = self.sent_from
                                        message['To'] = toEmail
                                        message['Subject'] = 'Making Buy Order Failed'
                                        # save this issue in mongodb
                                        content = {
                                            'subject': message['Subject'],
                                            'content': body,
                                            'created_at':  datetime.today().strftime('%Y-%m-%d-%H:%M:%S')
                                        }
                                        issueCollection = stockDB["Email"]
                                        issueCollection.insert_one(
                                            content)
                                        # The body and the attachments for the mail
                                        message.attach(
                                            MIMEText(body, 'plain'))

                                        try:
                                            requests.get(toSignalUrl +
                                                         body.replace("#", ""))
                                        except Exception as ex:
                                            print("Signal went error", ex)
                                            self.logError(
                                                "Signal went error "+str(ex)+" "+strategyName)
                                        try:
                                            smtp_server = smtplib.SMTP_SSL(
                                                'smtp.gmail.com', 465)
                                            smtp_server.ehlo()
                                            smtp_server.login(
                                                self.gmail_user, self.gmail_password)
                                            email_text = message.as_string()
                                            smtp_server.sendmail(
                                                self.sent_from, toEmail, email_text)
                                            smtp_server.close()
                                            print(
                                                "Email sent successfully!")
                                            self.logInfo(
                                                "Email sent successfully! "+strategyName)
                                        except Exception as ex:
                                            print(
                                                "Email sending failed", ex)
                                            self.logError(
                                                "Email sending failed "+str(ex)+" "+strategyName)
                                    break
                                time.sleep(self.requestCheckInterval)

            if checkedTime == 4:  # check old orders make sell order and
                currentTimestamp = datetime.now().timestamp()
                currentDate = datetime.fromtimestamp(
                    int(currentTimestamp-self.enterDate*24*3600), tz=self.newyork_timezone
                )
                enterFromDate = currentDate.strftime("%Y-%m-%d")
                currentDate = datetime.fromtimestamp(
                    int(currentTimestamp+24*3600), tz=self.newyork_timezone
                )
                enterToDate = currentDate.strftime("%Y-%m-%d")
                tdOrderStateList4pm = None

                while True:
                    currentTimeStamp = datetime.now().timestamp()
                    if (currentTimeStamp - self.lastAPICallTime) >= self.requestInterval:
                        self.lastAPICallTime = currentTimeStamp
                        try:
                            tdOrderStateList4pm = self.tdInstance.get_orders_query(
                                account=accountId, to_entered_time=enterToDate, from_entered_time=enterFromDate)  # get all order list from TD
                            print("get TD history of account ID: ",
                                  accountId, strategyName)
                            self.logInfo(
                                "Get TD history of account ID: " + accountId + " " + strategyName)
                        except Exception as e:
                            print(e)
                            # send email
                            body = 'Hi '+greeting+', Getting TD history has failed for account ID = ' +\
                                accountId+'. ' + str(e)
                            self.logError(body)
                            message = MIMEMultipart()
                            message['From'] = self.sent_from
                            message['To'] = toEmail
                            message['Subject'] = 'TD API Failed'
                            # save this issue in mongodb
                            content = {
                                'subject': message['Subject'],
                                'content': body,
                                'created_at':  datetime.today().strftime('%Y-%m-%d-%H:%M:%S')
                            }
                            stockDB = self.dbClient[self.SymbolDBName]
                            issueCollection = stockDB["Email"]
                            issueCollection.insert_one(
                                content)
                            # The body and the attachments for the mail
                            message.attach(
                                MIMEText(body, 'plain'))
                            try:
                                requests.get(
                                    toSignalUrl+body.replace("#", ""))
                            except Exception as ex:
                                print("Signal went error", ex)
                                self.logError(
                                    "TD order history error Signal went error "+str(ex))
                            try:
                                smtp_server = smtplib.SMTP_SSL(
                                    'smtp.gmail.com', 465)
                                smtp_server.ehlo()
                                smtp_server.login(
                                    self.gmail_user, self.gmail_password)
                                email_text = message.as_string()
                                smtp_server.sendmail(
                                    self.sent_from, toEmail, email_text)
                                smtp_server.close()
                                print(
                                    "Email sent successfully!")
                                self.logInfo(
                                    " TD order history error Email sent successfully!")
                            except Exception as ex:
                                print(
                                    "Email sending failed", ex)
                                self.logError(
                                    "TD order history error Email sending failed "+str(ex))
                        break
                    time.sleep(self.requestCheckInterval)

                if tdOrderStateList4pm == None:
                    continue
                # try:
                #     tdOrderStateList4pm = self.tdOrderStateList[accountId]
                # except KeyError:
                #     print("TD order is empty for account id "+accountId)
                #     self.logInfo("TD order is empty for account id "+accountId)
                #     tdOrderStateList4pm = None
                query = {"strategyName": strategyName, "state": {
                    "$nin": ["FILLED", "CANCELED", "REJECTED"]}, "timestamp": {"$gte": int(currentTimestamp-self.enterDate*24*3600)}}
                # get orders from DB with query
                stockDB = self.dbClient[self.SymbolDBName]
                collection = stockDB["OrderList"]
                mongoDBOrderList = collection.find(
                    query).sort("timestamp", pymongo.ASCENDING)

                if mongoDBOrderList != None and tdOrderStateList4pm != None:
                    for mongoItem in mongoDBOrderList:
                        for tdOrderItem in tdOrderStateList4pm:
                            if tdOrderItem["orderId"] == int(mongoItem["order_id"]):
                                # sell order
                                if tdOrderItem["orderLegCollection"][0]["instruction"] == "SELL" or tdOrderItem["orderLegCollection"][0]["instruction"] == "BUY_TO_COVER":
                                    # update sell order state
                                    newValues = {
                                        "$set": {"state": tdOrderItem["status"], "timestamp": datetime.now().timestamp()}}
                                    collection = stockDB["OrderList"]
                                    collection.update_one(
                                        {"order_id": str(tdOrderItem["orderId"])}, newValues)
                                    if tdOrderItem["status"] == "CANCELED" or tdOrderItem["status"] == "REJECTED":
                                        # second sell order failed
                                        if mongoItem["orderType"] == "MARKET_ON_CLOSE":
                                            failedSecondOrderInfo = {
                                                "strategyName": strategyName,
                                                "account_id": accountId,
                                                "order_id": tdOrderItem["orderId"],
                                                "orderType": mongoItem["orderType"],
                                                "instruction": mongoItem["instruction"],
                                                "symbol": mongoItem["symbol"],
                                                "quantity": mongoItem["quantity"],
                                                "year": self.year,
                                                "month": self.month,
                                                "date": self.date,
                                                "state": tdOrderItem["status"],
                                                "timestamp": datetime.now().timestamp()
                                            }
                                            failedSellOrderCollection = stockDB["FailedSellOrderList"]
                                            failedSellOrderCollection.insert_one(
                                                failedSecondOrderInfo)
                                            print("Second Sell Order "+tdOrderItem["status"],
                                                  mongoItem["order_id"], strategyName)
                                            # send email
                                            body = 'Hi '+greeting+', Order #' + \
                                                mongoItem["order_id"]+' for strategy `'+strategyName+'` for stock `' + \
                                                mongoItem["symbol"] + \
                                                '` has failed to trigger a sell order. Please check. account Id = '+accountId+'.'
                                            self.logError(body)
                                            message = MIMEMultipart()
                                            message['From'] = self.sent_from
                                            message['To'] = toEmail
                                            message['Subject'] = 'Second Sell Order Rejected or Canceled'
                                            # save this issue in mongodb
                                            content = {
                                                'subject': message['Subject'],
                                                'content': errorTxt,
                                                'created_at':  datetime.today().strftime('%Y-%m-%d-%H:%M:%S')
                                            }
                                            issueCollection = stockDB["Email"]
                                            issueCollection.insert_one(
                                                content)
                                            # The body and the attachments for the mail
                                            message.attach(
                                                MIMEText(body, 'plain'))

                                            try:
                                                requests.get(
                                                    toSignalUrl+body.replace("#", ""))
                                            except Exception as ex:
                                                print("Signal went error", ex)
                                                self.logError(
                                                    "Signal went error "+str(ex)+" "+strategyName)
                                            try:
                                                smtp_server = smtplib.SMTP_SSL(
                                                    'smtp.gmail.com', 465)
                                                smtp_server.ehlo()
                                                smtp_server.login(
                                                    self.gmail_user, self.gmail_password)
                                                email_text = message.as_string()
                                                smtp_server.sendmail(
                                                    self.sent_from, toEmail, email_text)
                                                smtp_server.close()
                                                print(
                                                    "Email sent successfully!")
                                                self.logInfo(
                                                    "Email sent successfully! "+strategyName)
                                            except Exception as ex:
                                                print(
                                                    "Email sending failed", ex)
                                                self.logError(
                                                    "Email sending failed "+str(ex)+" "+strategyName)
                                        else:  # first sell order rejected or canceled
                                            # send email
                                            failedFirstOrderInfo = {
                                                "strategyName": strategyName,
                                                "account_id": accountId,
                                                "order_id": tdOrderItem["orderId"],
                                                "orderType": mongoItem["orderType"],
                                                "instruction": mongoItem["instruction"],
                                                "symbol": mongoItem["symbol"],
                                                "quantity": mongoItem["quantity"],
                                                "year": self.year,
                                                "month": self.month,
                                                "date": self.date,
                                                "state": tdOrderItem["status"],
                                                "timestamp": datetime.now().timestamp()
                                            }
                                            failedSellOrderCollection = stockDB["FailedSellOrderList"]
                                            failedSellOrderCollection.insert_one(
                                                failedFirstOrderInfo)
                                            print("First Sell Order "+tdOrderItem["status"],
                                                  mongoItem["order_id"], strategyName)
                                            # send email
                                            body = 'Hi '+greeting+', Order #' + \
                                                mongoItem["order_id"]+' for strategy `'+strategyName+'` for stock `' + \
                                                mongoItem["symbol"] + \
                                                '` has failed to trigger a sell order. Please check. account Id = '+accountId+'.'
                                            self.logError(body)
                                            message = MIMEMultipart()
                                            message['From'] = self.sent_from
                                            message['To'] = toEmail
                                            message['Subject'] = 'First Sell Order Rejected or Canceled'
                                            # save this issue in mongodb
                                            content = {
                                                'subject': message['Subject'],
                                                'content': body,
                                                'created_at':  datetime.today().strftime('%Y-%m-%d-%H:%M:%S')
                                            }
                                            issueCollection = stockDB["Email"]
                                            issueCollection.insert_one(
                                                content)
                                            # The body and the attachments for the mail
                                            message.attach(
                                                MIMEText(body, 'plain'))

                                            try:
                                                requests.get(
                                                    toSignalUrl+body.replace("#", ""))
                                            except Exception as ex:
                                                print("Signal went error", ex)
                                                self.logError(
                                                    "Signal went error "+str(ex)+" "+strategyName)
                                            try:
                                                smtp_server = smtplib.SMTP_SSL(
                                                    'smtp.gmail.com', 465)
                                                smtp_server.ehlo()
                                                smtp_server.login(
                                                    self.gmail_user, self.gmail_password)
                                                email_text = message.as_string()
                                                smtp_server.sendmail(
                                                    self.sent_from, toEmail, email_text)
                                                smtp_server.close()
                                                print(
                                                    "Email sent successfully!")
                                                self.logInfo(
                                                    "Email sent successfully! "+strategyName)
                                            except Exception as ex:
                                                print(
                                                    "Email sending failed", ex)
                                                self.logError(
                                                    "Email sending failed "+str(ex)+" "+strategyName)
                                    elif tdOrderItem["status"] == "FILLED":
                                        # any type sell order successed, sending email
                                        if mongoItem["orderType"] == "LIMIT":
                                            if mongoItem["type"] == 0:  # long case
                                                profit = float(tdOrderItem['price']) * float(tdOrderItem["filledQuantity"]) - float(
                                                    mongoItem["boughtPrice"]) * float(mongoItem["quantity"])
                                            else:
                                                profit = float(
                                                    mongoItem["boughtPrice"]) * float(mongoItem["quantity"]) - float(tdOrderItem['price']) * float(tdOrderItem["filledQuantity"])
                                            actualExit = "Profit%"
                                            if mongoItem["isATR"] == 1:
                                                actualExit = "ATR"
                                            newValues = {
                                                "$set": {
                                                    "profit": profit,
                                                    "filledPrice": tdOrderItem['price'],
                                                    "filledQuantity": tdOrderItem["filledQuantity"],
                                                    "closeTime": tdOrderItem["closeTime"],
                                                    "actualExit": actualExit
                                                }
                                            }
                                            collection = stockDB["OrderList"]
                                            collection.update_one(
                                                {"order_id": str(tdOrderItem["orderId"])}, newValues)
                                        else:
                                            if mongoItem["type"] == 0:  # long case
                                                profit = float(tdOrderItem['orderActivityCollection'][0]['executionLegs'][0]['price'])*float(
                                                    tdOrderItem["filledQuantity"]) - float(mongoItem["boughtPrice"])*float(mongoItem["quantity"])
                                            else:
                                                profit = float(mongoItem["boughtPrice"])*float(mongoItem["quantity"]) - float(tdOrderItem['orderActivityCollection'][0]['executionLegs'][0]['price'])*float(
                                                    tdOrderItem["filledQuantity"])
                                            newValues = {
                                                "$set": {
                                                    "profit": profit,
                                                    "price": tdOrderItem['orderActivityCollection'][0]['executionLegs'][0]['price'],
                                                    "filledPrice": tdOrderItem['orderActivityCollection'][0]['executionLegs'][0]['price'],
                                                    "filledQuantity": tdOrderItem["filledQuantity"],
                                                    "closeTime": tdOrderItem["closeTime"],
                                                    "actualExit": "Market"
                                                }
                                            }
                                            collection = stockDB["OrderList"]
                                            collection.update_one(
                                                {"order_id": str(tdOrderItem["orderId"])}, newValues)
                                        body = 'Hi '+greeting+', Order #' + \
                                            mongoItem["order_id"]+' for strategy `'+strategyName+'` for stock `' + \
                                            mongoItem["symbol"]+'` has filled. And the profit was USD ' + \
                                            str(profit)+'. Please check. account Id = ' + \
                                            accountId+'.\n'
                                        body = body + \
                                            self.getStrategyProfitInfo(
                                                strategyName)
                                        self.logInfo(body)
                                        message = MIMEMultipart()
                                        message['From'] = self.sent_from
                                        message['To'] = toEmail
                                        message['Subject'] = 'Sell Order Filled'
                                        # save this issue in mongodb
                                        content = {
                                            'subject': message['Subject'],
                                            'content': body,
                                            'created_at':  datetime.today().strftime('%Y-%m-%d-%H:%M:%S')
                                        }
                                        issueCollection = stockDB["Email"]
                                        issueCollection.insert_one(content)
                                        # The body and the attachments for the mail
                                        message.attach(MIMEText(body, 'plain'))

                                        try:
                                            body = body.replace("$", "")
                                            requests.get(
                                                toSignalUrl+body.replace("#", ""))
                                        except Exception as ex:
                                            print("Signal went error", ex)
                                            self.logError(
                                                "Signal went error "+str(ex)+" "+strategyName)
                                        try:
                                            smtp_server = smtplib.SMTP_SSL(
                                                'smtp.gmail.com', 465)
                                            smtp_server.ehlo()
                                            smtp_server.login(
                                                self.gmail_user, self.gmail_password)
                                            email_text = message.as_string()
                                            smtp_server.sendmail(
                                                self.sent_from, toEmail, email_text)
                                            smtp_server.close()
                                            print(
                                                "Email sent successfully!")
                                            self.logInfo(
                                                "Email sent successfully! "+strategyName)
                                        except Exception as ex:
                                            print(
                                                "Email sending failed", ex)
                                            self.logError(
                                                "Email sending failed "+str(ex)+" "+strategyName)

                                # buy order
                                if tdOrderItem["orderLegCollection"][0]["instruction"] == "BUY" or tdOrderItem["orderLegCollection"][0]["instruction"] == "SELL_SHORT":
                                    # buy order successed then make sell order
                                    if tdOrderItem["status"] == "FILLED":
                                        # make sell order
                                        firstSellOrder = Order()
                                        firstSellOrder.order_session(
                                            session=ORDER_SESSION.NORMAL)
                                        firstSellOrder.order_type(
                                            order_type=ORDER_TYPE.LIMIT)
                                        firstSellOrder.order_duration(
                                            duration=DURATION.GOOD_TILL_CANCEL)
                                        firstSellOrder.order_strategy_type(
                                            order_strategy_type=ORDER_STRATEGY_TYPE.SINGLE)
                                        boughtPrice = tdOrderItem["orderActivityCollection"][0]["executionLegs"][0]["price"]
                                        if mongoItem["isATR"] == 1:  # atr value case
                                            price = float(boughtPrice)+float(mongoItem["atrValue"])*float(mongoItem['atr'])
                                            if price >= float(boughtPrice)*2:
                                                price = float(boughtPrice) * 1.05
                                        else:  # profit percents case
                                            price = float(boughtPrice)*(1+float(mongoItem["profitPercent"])*0.01)
                                        if price < 1:
                                            price = float(
                                                "{:.4f}".format(price))
                                        else:
                                            price = float(
                                                "{:.2f}".format(price))
                                        firstSellOrder.order_price(
                                            price=price)
                                        firstSellOrderLeg = OrderLeg()
                                        if mongoItem["type"] == 0:  # long case
                                            firstSellOrderLeg.order_leg_instruction(
                                                instruction=ORDER_INSTRUCTIONS.SELL)
                                        else:
                                            firstSellOrderLeg.order_leg_instruction(
                                                instruction=ORDER_INSTRUCTIONS.BUY_TO_COVER)
                                        firstSellOrderLeg.order_leg_asset(
                                            asset_type=ORDER_ASSET_TYPE.EQUITY, symbol=mongoItem["symbol"])
                                        firstSellOrderLeg.order_leg_quantity(
                                            quantity=mongoItem["quantity"])
                                        firstSellOrder.add_order_leg(
                                            order_leg=firstSellOrderLeg)

                                        while True:
                                            currentTimeStamp = datetime.now().timestamp()
                                            if (currentTimeStamp - self.lastAPICallTime) >= self.requestInterval:
                                                self.lastAPICallTime = currentTimeStamp
                                                try:
                                                    result = self.tdInstance.place_order(
                                                        order=firstSellOrder, account=accountId)
                                                    # update buy order state
                                                    newValues = {
                                                        "$set": {"price": tdOrderItem["orderActivityCollection"][0]["executionLegs"][0]["price"], "state": tdOrderItem["status"], "timestamp": datetime.now().timestamp()}}
                                                    collection = stockDB["OrderList"]
                                                    collection.update_one(
                                                        {"order_id": str(tdOrderItem["orderId"])}, newValues)
                                                    request = json.loads(
                                                        result["request_body"])
                                                    print(
                                                        "Make First Sell Order", result["order_id"], request["orderLegCollection"][0]["instrument"]["symbol"], strategyName)
                                                    self.logInfo("Make First Sell Order " + str(result["order_id"])+" "+str(
                                                        request["orderLegCollection"][0]["instrument"]["symbol"])+" "+strategyName)

                                                    firstSellOrderInfo = {
                                                        "strategyName": strategyName,
                                                        "account_id": accountId,
                                                        "order_id": result["order_id"],
                                                        "Date": result["headers"]["Date"],
                                                        "orderType": request["orderType"],
                                                        "orderStrategyType": request["orderStrategyType"],
                                                        "duration": request["duration"],
                                                        # buy or sell
                                                        "instruction": request["orderLegCollection"][0]["instruction"],
                                                        "symbol": request["orderLegCollection"][0]["instrument"]["symbol"],
                                                        "quantity": request["orderLegCollection"][0]["quantity"],
                                                        "price": price,
                                                        "profit": 0,
                                                        "isATR": mongoItem["isATR"],
                                                        "orderLegCollection": request["orderLegCollection"],
                                                        "boughtPrice": tdOrderItem["orderActivityCollection"][0]["executionLegs"][0]["price"],
                                                        "parentOrderId": mongoItem["order_id"],
                                                        "year": self.year,
                                                        "month": self.month,
                                                        "date": self.date,
                                                        "type": mongoItem['type'],
                                                        "state": "None",
                                                        "timestamp": datetime.now().timestamp()
                                                    }
                                                    # stockDB = self.dbClient[self.SymbolDBName]
                                                    # collection = stockDB["OrderList"]
                                                    collection = stockDB["OrderList"]
                                                    collection.insert_one(
                                                        firstSellOrderInfo)
                                                except Exception as e:
                                                    # send email
                                                    body = 'Hi '+greeting+', Making order has failed for strategy `'+strategyName+'` for stock `' + \
                                                        mongoItem["symbol"] + \
                                                        '`. account Id = ' + \
                                                        accountId+'. ' + str(e)
                                                    self.logError(body)
                                                    message = MIMEMultipart()
                                                    message['From'] = self.sent_from
                                                    message['To'] = toEmail
                                                    message['Subject'] = 'Making First Sell Order Failed'
                                                    # save this issue in mongodb
                                                    content = {
                                                        'subject': message['Subject'],
                                                        'content': body,
                                                        'created_at':  datetime.today().strftime('%Y-%m-%d-%H:%M:%S')
                                                    }
                                                    issueCollection = stockDB["Email"]
                                                    issueCollection.insert_one(
                                                        content)
                                                    # The body and the attachments for the mail
                                                    message.attach(
                                                        MIMEText(body, 'plain'))

                                                    try:
                                                        requests.get(
                                                            toSignalUrl+body.replace("#", ""))
                                                    except Exception as ex:
                                                        print(
                                                            "Signal went error", ex)
                                                        self.logError(
                                                            "Signal went error "+str(ex)+" "+strategyName)
                                                    try:
                                                        smtp_server = smtplib.SMTP_SSL(
                                                            'smtp.gmail.com', 465)
                                                        smtp_server.ehlo()
                                                        smtp_server.login(
                                                            self.gmail_user, self.gmail_password)
                                                        email_text = message.as_string()
                                                        smtp_server.sendmail(
                                                            self.sent_from, toEmail, email_text)
                                                        smtp_server.close()
                                                        print(
                                                            "Email sent successfully!")
                                                        self.logInfo(
                                                            "Email sent successfully! "+strategyName)
                                                    except Exception as ex:
                                                        print(
                                                            "Email sending failed", ex)
                                                        self.logError(
                                                            "Email sending failed "+str(ex)+" "+strategyName)
                                                break
                                            time.sleep(
                                                self.requestCheckInterval)
                                    # buy order failed or not filled then cancel
                                    elif tdOrderItem["status"] != "REJECTED" and tdOrderItem["status"] != "CANCELED":
                                        # update state to CANCELED
                                        cancelResult = None
                                        while True:
                                            currentTimeStamp = datetime.now().timestamp()
                                            if (currentTimeStamp - self.lastAPICallTime) >= self.requestInterval:
                                                self.lastAPICallTime = currentTimeStamp
                                                try:
                                                    cancelResult = self.tdInstance.cancel_order(
                                                        account=accountId, order_id=mongoItem["order_id"])
                                                    newValues = {
                                                        "$set": {"state": "CANCELED", "timestamp": datetime.now().timestamp()}}
                                                    collection = stockDB["OrderList"]
                                                    collection.update_one(
                                                        {"order_id": str(tdOrderItem["orderId"])}, newValues)
                                                    print(
                                                        "Cancel Buy Order ", tdOrderItem["orderId"], mongoItem["symbol"], strategyName)
                                                    self.logInfo("Cancel Buy Order " + str(
                                                        tdOrderItem["orderId"])+" " + mongoItem["symbol"]+" "+strategyName + " "+str(e))
                                                except Exception as e:
                                                    print(
                                                        "Cancel Buy Order By Failed", tdOrderItem["orderId"], mongoItem["symbol"], strategyName)
                                                    self.logError("Cancel Buy Order By Failed " + str(
                                                        tdOrderItem["orderId"])+" "+str(mongoItem["symbol"])+" " + strategyName)
                                                break
                                            time.sleep(
                                                self.requestCheckInterval)
                                    else:
                                        # update sell order state
                                        newValues = {
                                            "$set": {"state": tdOrderItem["status"], "timestamp": datetime.now().timestamp()}}
                                        collection = stockDB["OrderList"]
                                        collection.update_one(
                                            {"order_id": str(tdOrderItem["orderId"])}, newValues)
        self.threadList[strategyName] = None
        self.runningStateLable.config(text="Idle now", fg="#00f")
        messagebox.showinfo(
            title=None, message=strategyName+" process canceled.")

    def onClickStopExitAllBtn(self):
        index = self.strategyComboBoxInLive.current()
        if index < 0:
            messagebox.showinfo(title=None, message="Please select strategy")
            return
        strategyName = self.strategyNamesArray[index]
        if strategyName in self.threadList:
            currentThread = self.threadList[strategyName]
            if currentThread != None:
                self.threadStateList[strategyName] = False
        else:
            messagebox.showinfo(
                title=None, message=strategyName+" process is not in running.")

    def onClickSaveBtn(self):
        selectedPosition = self.strategyComboBoxInLive.current()
        if selectedPosition < 0:
            messagebox.showinfo(title=None, message="Please select strategy")
            return

        strategyName = self.strategyNamesArray[selectedPosition]
        if strategyName in self.threadList and self.threadList[strategyName] != None and self.threadStateList[strategyName] == True:
            messagebox.showinfo(
                title=None, message="Process is running already")
            return

        if self.isATR.get() == 1 and self.atrValueEntry.get() == "":
            messagebox.showinfo(
                title=None, message="Please enter ATR value")
            return

        if self.isProfit.get() == 1 and self.profitValueEntry.get() == "":
            messagebox.showinfo(
                title=None, message="Please enter Profit% value")
            return

        if self.isDayExit.get() == 1 and self.dayExitEntry.get() == "":
            messagebox.showinfo(
                title=None, message="Please enter Exit Day")
            return

        if self.isExitAPI.get() == 1 and self.exitAPIEntry.get() == "":
            messagebox.showinfo(
                title=None, message="Please enter Exit API")
            return

        tmpData = {
            'strategyName': strategyName,
            'accountName':  self.selectedAccountName.get(),
            'position': self.positionComboBoxInLive.current(),
            'sortBy': self.sortByComboBoxInLive.current(),
            'sortOrder': self.sortOrderComboBoxInLive.current(),
            'atr': self.atrValueEntry.get(),
            'profit': self.profitValueEntry.get(),
            'dayExit': self.dayExitEntry.get(),
            'exitAPI': self.exitAPIEntry.get(),
            'isATR': self.isATR.get(),
            'isProfit': self.isProfit.get(),
            'isDayExit': self.isDayExit.get(),
            'isExitAPI': self.isExitAPI.get(),
            'instruction': self.instructionTypeComboBoxInLive.current()
        }
        stockDB = self.dbClient[self.SymbolDBName]
        collection = stockDB["SavedStrategy"]
        myquery = {"strategyName": strategyName}
        collection.delete_one(myquery)
        collection.insert_one(tmpData)
        messagebox.showinfo(title=None, message="Saved Successfully")

    def onClickStartBtn(self):
        selectedPosition = self.strategyComboBoxInLive.current()
        if selectedPosition < 0:
            messagebox.showinfo(title=None, message="Please select strategy")
            return
        if len(self.accountInfos) == 0:
            messagebox.showinfo(
                title=None, message="Please set Account Id and Start Total Amount and Max Strategy Number")
            return
        selectedPosition = self.strategyComboBoxInLive.current()
        if selectedPosition < 0:
            messagebox.showinfo(title=None, message="Please select strategy")
            return
        strategyName = self.strategyNamesArray[selectedPosition]
        if (
            strategyName in self.threadList
            and self.threadStateList[strategyName] == True
            or strategyName in self.threadList and self.threadList[strategyName] != None
        ):
            messagebox.showinfo(
                title=None, message="Process is running already")
            return

        if self.isATR.get() == 1 and self.atrValueEntry.get() == "":
            messagebox.showinfo(
                title=None, message="Please enter ATR value")
            return

        if self.isProfit.get() == 1 and self.profitValueEntry.get() == "":
            messagebox.showinfo(
                title=None, message="Please enter Profit% value")
            return

        if self.isDayExit.get() == 1 and self.dayExitEntry.get() == "":
            messagebox.showinfo(
                title=None, message="Please enter Exit Day")
            return

        if self.isExitAPI.get() == 1 and self.exitAPIEntry.get() == "":
            messagebox.showinfo(
                title=None, message="Please enter Exit API")
            return

        tmpData = {
            'strategyName': strategyName,
            'accountName':  self.selectedAccountName.get(),
            'position': self.positionComboBoxInLive.current(),
            'sortBy': self.sortByComboBoxInLive.current(),
            'sortOrder': self.sortOrderComboBoxInLive.current(),
            'atr': self.atrValueEntry.get(),
            'profit': self.profitValueEntry.get(),
            'dayExit': self.dayExitEntry.get(),
            'exitAPI': self.exitAPIEntry.get(),
            'isATR': self.isATR.get(),
            'isProfit': self.isProfit.get(),
            'isDayExit': self.isDayExit.get(),
            'isExitAPI': self.isExitAPI.get(),
            'instruction': self.instructionTypeComboBoxInLive.current()
        }
        stockDB = self.dbClient[self.SymbolDBName]
        collection = stockDB["SavedStrategy"]
        myquery = {"strategyName": strategyName}
        collection.delete_one(myquery)
        collection.insert_one(tmpData)

        selectedPosition = self.strategyComboBoxInLive.current()
        print(selectedPosition)
        print(strategyName)
        print(self.strategyEntryAPIArray[selectedPosition])
        orderThread = threading.Thread(
            target=self.makeProcessOrder,
            args=(self, strategyName,
                  self.strategyEntryAPIArray[selectedPosition]),
            daemon=True
        )
        self.startegyParametersList[strategyName] = tmpData
        self.threadList[strategyName] = orderThread
        self.threadStateList[strategyName] = True
        self.threadList[strategyName].start()

    def onClickRefreshBtn(self):
        utcDateNow = datetime.now(self.utc_timezone)
        month = utcDateNow.month
        day = utcDateNow.day
        if month < 10:
            month = "0"+str(month)
        else:
            month = str(month)
        if day < 10:
            day = "0"+str(day)
        else:
            day = str(day)
        currentUTCDateStr = month+"/"+day+"/"+str(utcDateNow.year)
        selectedPosition = self.strategyComboBoxInLive.current()
        if selectedPosition < 0:
            messagebox.showinfo(title=None, message="Please select strategy")
            return
        self.currentAPIEntryTable.delete(
            *self.currentAPIEntryTable.get_children())
        strategyName = self.strategyNamesArray[self.strategyComboBoxInLive.current(
        )]
        response = None
        try:
            response = requests.get(
                self.strategyEntryAPIArray[self.strategyComboBoxInLive.current()], timeout=8)
        except requests.exceptions.Timeout:
            print("Time Out in EntryAPI of " + strategyName)
        except requests.exceptions.HTTPError:
            print("HTTPError in EntryAPI of " + strategyName)
        except requests.exceptions.RequestException as e:
            print("RequestException in EntryAPI of " + strategyName)
        except requests.exceptions.TooManyRedirects:
            print("TooManyRedirects in EntryAPI of " + strategyName)
        if response == None:
            return
        result = []
        print(currentUTCDateStr)
        for data in response.text.splitlines():
            item = data.split("|")
            # if item[2].startswith(currentUTCDateStr) == False:
            #     continue
            result.append(item)
        response.close()
        if(self.sortOrderComboBoxInLive.current() == 0):
            result.sort(key=self.sortKey, reverse=False)
        else:
            result.sort(key=self.sortKey, reverse=True)
        iid = 0

        for item in result:  # [0:(self.positionComboBoxInLive.current()+1)]:
            # stock information
            self.currentAPIEntryTable.insert(
                parent="",
                index="end",
                iid=iid,
                text=f"{iid+1}",
                values=(
                    item[0],
                    item[1],
                    item[2],
                    item[3],
                    item[4],
                    item[5],
                    item[6],
                    item[7],
                    item[8],
                    item[9],
                    item[10],
                    item[11],
                    item[12],
                ),
            )
            iid += 1

    def onCheckIsATR(self):
        print(self.isProfit.get())
        if self.isProfit.get() == 1:
            self.isProfit.set(0)

    def onCheckIsProfit(self):
        print(self.isATR.get())
        if self.isATR.get() == 1:
            self.isATR.set(0)

    def onCheckIsDayExit(self):
        print("isDayExit")

    def onCheckIsExitAPI(self):
        print("isExitAPI")

    def onItemSelectStrategyComboBoxInLive(self, event):
        selectedStrategyName = event.widget.get()
        stockDB = self.dbClient[self.SymbolDBName]
        collection = stockDB["SavedStrategy"]
        myquery = {"strategyName": selectedStrategyName}
        savedStrategy = collection.find_one(myquery)
        if savedStrategy == None:
            savedStrategy = {
                'position': 0,
                'accountName': "",
                'sortBy': 0,
                'sortOrder': 0,
                'atr': "",
                'profit': "",
                'dayExit': "",
                'exitAPI': "",
                'isATR': 0,
                'isProfit': 0,
                'isDayExit': 0,
                'isExitAPI': 0,
                'instruction': 0
            }
        try:
            self.accountIdComboBoxInLive.current(self.accountNames.index(savedStrategy["accountName"]))
        except Exception as e:
            self.accountIdComboBoxInLive.current(0)
        self.positionComboBoxInLive.current(savedStrategy['position'])
        self.sortByComboBoxInLive.current(savedStrategy['sortBy'])
        self.sortOrderComboBoxInLive.current(savedStrategy['sortOrder'])
        self.atrValueEntry.delete(0, END)
        self.profitValueEntry.delete(0, END)
        self.dayExitEntry.delete(0, END)
        self.exitAPIEntry.delete(0, END)

        self.atrValueEntry.insert(0, savedStrategy['atr'])
        self.profitValueEntry.insert(0, savedStrategy['profit'])
        self.dayExitEntry.insert(0, savedStrategy['dayExit'])
        self.exitAPIEntry.insert(0, savedStrategy['exitAPI'])

        self.isATR.set(savedStrategy['isATR'])
        self.isProfit.set(savedStrategy['isProfit'])
        self.isDayExit.set(savedStrategy['isDayExit'])
        self.isExitAPI.set(savedStrategy['isExitAPI'])
        self.instructionTypeComboBoxInLive.current(
            savedStrategy['instruction'])

        selectedPosition = self.strategyComboBoxInLive.current()
        strategyName = self.strategyNamesArray[selectedPosition]
        if strategyName in self.threadList and self.threadList[strategyName] != None and self.threadStateList[strategyName] == True:
            self.runningStateLable.config(text='Running now', fg="#f00")
        else:
            self.runningStateLable.config(text='Idle now', fg="#00f")

        collection = stockDB["OrderList"]
        myquery = {"strategyName": selectedStrategyName, "state": "FILLED"}
        orderHistory = collection.find(myquery).sort(
            "timestamp", pymongo.DESCENDING)
        totalProfit = 0
        totalTrade = 0
        profitTrade = 0
        totalAbsProfit = 0
        minusAbsProfit = 0
        profitFactor = "0.0"
        if orderHistory != None:
            # calculate the profit
            for successedOrder in orderHistory:
                # Sell Filled Order
                if successedOrder["instruction"] == "SELL" or successedOrder["instruction"] == "BUY_TO_COVER":
                    if successedOrder["type"] == 0:  # long case
                        profit = float(successedOrder["filledPrice"])*float(successedOrder["filledQuantity"]) - float(
                            successedOrder["boughtPrice"])*float(successedOrder["quantity"])
                    else:  # short case
                        profit = float(successedOrder["boughtPrice"])*float(successedOrder["quantity"]) - float(
                            successedOrder["filledPrice"])*float(successedOrder["filledQuantity"])

                    if profit > 0:
                        profitTrade += 1
                    else:
                        minusAbsProfit += abs(profit)
                    totalProfit += profit
                    totalAbsProfit += abs(profit)
                else:  # Buy Filled Order
                    totalTrade += 1
            if minusAbsProfit > 0:
                profitFactor = "{:.2f}".format(totalProfit/minusAbsProfit)
        self.strategyTradesTxt.config(text=str(totalTrade))
        self.strategyTotalProfitTxt.config(text="{:.4f}".format(totalProfit))
        self.strategyProfitableTradesTxt.config(text=str(profitTrade))
        self.strategyProfitFactorTxt.config(text=profitFactor)

        # for bottom table
        collection = stockDB["OrderList"]
        myquery = {"strategyName": selectedStrategyName}
        allOrderList = collection.find(myquery).sort(
            "timestamp", pymongo.ASCENDING)
        self.orderTreeView.delete(
            *self.orderTreeView.get_children())

        strategyParams = {
            'strategyName': strategyName,
            'accountName':  self.accountIdComboBoxInLive.current(),
            'position': self.positionComboBoxInLive.current(),
            'sortBy': self.sortByComboBoxInLive.current(),
            'sortOrder': self.sortOrderComboBoxInLive.current(),
            'atr': self.atrValueEntry.get(),
            'profit': self.profitValueEntry.get(),
            'dayExit': self.dayExitEntry.get(),
            'exitAPI': self.exitAPIEntry.get(),
            'isATR': self.isATR.get(),
            'isProfit': self.isProfit.get(),
            'isDayExit': self.isDayExit.get(),
            'isExitAPI': self.isExitAPI.get(),
            'instruction': self.instructionTypeComboBoxInLive.current()
        }
        iid = 0
        orderHistoryArray = []
        for order in allOrderList:
            orderHistoryArray.append(order)
        for buyOrder in orderHistoryArray:
            if buyOrder["instruction"] == "BUY" and buyOrder["state"] == "FILLED":
                strategy = buyOrder["strategyName"]
                plannedExit = ""
                account = buyOrder["account_id"]
                entryOrder = buyOrder["order_id"]
                exitOrder = ""
                profitTarget1 = ""
                symbol = buyOrder["symbol"]
                entryDate = buyOrder["Date"]
                entryPrice = str(buyOrder["price"])
                entryShares = str(buyOrder["quantity"])
                exitTarget = ""
                exitDate = ""
                exitPrice = ""
                entryAmount = "{:.4f}".format(
                    float(entryPrice)*float(entryShares))
                exitAmount = ""
                actualProfit = ""
                actualExit = ""
                if buyOrder["isATR"] == 1:
                    plannedExit = "ATR"
                else:
                    plannedExit = "Profit"
                if strategyParams["isDayExit"] == 1:
                    plannedExit += ",DayExit"
                if strategyParams["isExitAPI"] == 1:
                    plannedExit += ",API Exit"

                sellOrderInfo = None
                for sellOrder in orderHistoryArray:
                    if sellOrder["instruction"] == "SELL":
                        if sellOrder["duration"] == "GOOD_TILL_CANCEL":
                            parentOrderId = None
                            if sellOrder["state"] != "CANCELED" and sellOrder["state"] != "REJECTED":
                                parentOrderId = sellOrder["parentOrderId"]
                        else:  # MOC sell order. find GTC order info
                            parentOrderId = None
                            subParentOrderId = sellOrder["parentOrderId"]
                            myquery = {"order_id": subParentOrderId}
                            firstOrderInfo = collection.find_one(myquery)
                            if firstOrderInfo != None:
                                parentOrderId = firstOrderInfo["parentOrderId"]
                        # it is this buyer order's sell order
                        if parentOrderId != None and parentOrderId == buyOrder["order_id"]:
                            sellOrderInfo = sellOrder
                            break

                if sellOrderInfo != None:
                    exitOrder = sellOrder["order_id"]
                    exitTarget = str(float(sellOrder["price"]))
                    if sellOrderInfo["state"] == "FILLED":
                        exitDate = sellOrder["closeTime"].replace(
                            "+0000", " UTC")
                        exitPrice = str(float(sellOrder["filledPrice"]))
                        exitAmount = "{:.4f}".format(
                            float(sellOrder["filledPrice"])*float(sellOrder["filledQuantity"]))
                        if sellOrder["type"] == 0:  # long case
                            actualProfit = "{:.4f}".format(float(sellOrder["filledPrice"])*float(
                                sellOrder["filledQuantity"]) - float(entryPrice)*float(entryShares))
                        else:
                            actualProfit = "{:.4f}".format(float(entryPrice)*float(entryShares) - float(sellOrder["filledPrice"])*float(
                                sellOrder["filledQuantity"]))
                        actualExit = sellOrder["actualExit"]

                self.orderTreeView.insert(
                    parent="",
                    index="end",
                    iid=iid,
                    text=f"{iid+1}",
                    values=(
                        symbol,
                        # strategy,
                        # plannedExit,
                        account,
                        entryOrder,
                        exitOrder,
                        # profitTarget1,
                        entryDate,
                        entryPrice,
                        entryShares,
                        exitTarget,
                        exitDate,
                        exitPrice,
                        entryAmount,
                        exitAmount,
                        actualProfit,
                        actualExit
                    ),
                )
                iid += 1

    def getStrategyProfitInfo(self, strategyName):
        stockDB = self.dbClient[self.SymbolDBName]
        collection = stockDB["OrderList"]
        myquery = {"strategyName": strategyName, "state": "FILLED"}
        orderHistory = collection.find(myquery).sort(
            "timestamp", pymongo.DESCENDING)
        totalProfit = 0
        sellFilledTrade = 0
        buyFilledTrade = 0
        profitTrade = 0
        minusAbsProfit = 0
        if orderHistory != None:
            # calculate the profit
            for successedOrder in orderHistory:
                # Sell Filled Order
                if successedOrder["instruction"] == "SELL" or successedOrder["instruction"] == "BUY_TO_COVER":
                    if successedOrder["type"] == 0:  # long case
                        profit = float(successedOrder["filledPrice"])*float(successedOrder["filledQuantity"]) - float(
                            successedOrder["boughtPrice"])*float(successedOrder["quantity"])
                    else:  # short case
                        profit = float(successedOrder["boughtPrice"])*float(successedOrder["quantity"]) - float(
                            successedOrder["filledPrice"])*float(successedOrder["filledQuantity"])

                    if profit > 0:
                        profitTrade += 1
                    else:
                        minusAbsProfit += abs(profit)
                    totalProfit += profit
                    sellFilledTrade += 1
                else:  # Buy Filled Order
                    buyFilledTrade += 1
        if minusAbsProfit == 0:
            profitFactor = "0.0"
        else:
            profitFactor = "{:.2f}".format(totalProfit/minusAbsProfit)
        result = "Strategy Summary\n" + "Profit: $" +\
            "{:.4f}".format(totalProfit) +\
            "     Profit Factor: "+profitFactor +\
            "     Total Trades: "+str(buyFilledTrade) +\
            "     Open Trades: " + str(buyFilledTrade-sellFilledTrade) +\
            "     Profitable Trades: " + \
            "{:.2f}%".format(profitTrade/buyFilledTrade*100)
        return result

    def addViewInLive(self):
        Label(self.tabLiveFrame, text="Strategy").grid(
            row=0, column=0,  pady=10)
        Label(self.tabLiveFrame, text="Positions").grid(
            row=0, column=1,  pady=10)
        Label(self.tabLiveFrame, text="Sort Order").grid(
            row=0, column=2,  pady=10)
        Label(self.tabLiveFrame, text="Sort By").grid(
            row=0, column=3,  pady=10)
        Label(self.tabLiveFrame, text="Account").grid(
            row=0, column=4,  pady=10)
        Label(self.tabLiveFrame, text="Instruction").grid(
            row=0, column=5,  pady=10)

        self.selectedStrategy = StringVar()
        self.strategyComboBoxInLive = ttk.Combobox(
            self.tabLiveFrame, textvariable=self.selectedStrategy
        )
        self.strategyComboBoxInLive["values"] = self.strategyNamesArray
        self.strategyComboBoxInLive["state"] = "readonly"  # normal
        # self.strategyComboBoxInLive.current(0)
        self.strategyComboBoxInLive.grid(row=1, column=0, padx=5)
        self.strategyComboBoxInLive.bind(
            "<<ComboboxSelected>>", self.onItemSelectStrategyComboBoxInLive
        )

        self.selectedPosition = IntVar()
        self.positionComboBoxInLive = ttk.Combobox(
            self.tabLiveFrame, textvariable=self.selectedPosition
        )
        self.positionComboBoxInLive["values"] = [
            1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  # self.currentStrategyNames
        self.positionComboBoxInLive["state"] = "readonly"  # normal
        self.positionComboBoxInLive.current(0)
        self.positionComboBoxInLive.grid(row=1, column=1, padx=5)

        self.selectedSortOrder = StringVar()
        self.sortOrderComboBoxInLive = ttk.Combobox(
            self.tabLiveFrame, textvariable=self.selectedSortOrder
        )
        # self.currentStrategyNames
        self.sortOrderComboBoxInLive["values"] = ['Increase', 'Decrease']
        self.sortOrderComboBoxInLive["state"] = "readonly"  # normal
        self.sortOrderComboBoxInLive.current(0)
        self.sortOrderComboBoxInLive.grid(row=1, column=2, padx=5)

        self.selectedSortBy = StringVar()
        self.sortByComboBoxInLive = ttk.Combobox(
            self.tabLiveFrame, textvariable=self.selectedSortBy
        )
        self.sortByComboBoxInLive["values"] = [
            # "Strategy",
            # "Trades",
            # "Profit($)",
            # "Profit Factor"
            "Symbol",
            "Price",
            "Time",
            "ATR(14)",
            "ROC(2)",
            "ROC(3)",
            "RS5",
            "RS10",
            "NATR(4)",
            "NATR(14)",
            "RSI(2)",
            "RSI(3)",
            "RSI(14)",
        ]  # self.currentStrategyNames
        self.sortByComboBoxInLive["state"] = "readonly"  # normal
        self.sortByComboBoxInLive.current(0)
        self.sortByComboBoxInLive.grid(row=1, column=3, padx=5)

        # Account Ids
        self.selectedAccountName = StringVar()
        self.accountIdComboBoxInLive = ttk.Combobox(
            self.tabLiveFrame, textvariable=self.selectedAccountName
        )
        self.accountIdComboBoxInLive["values"] = self.accountNames
        self.accountIdComboBoxInLive["state"] = "readonly"  # normal
        if len(self.accountNames) > 0:
            self.accountIdComboBoxInLive.current(0)
        self.accountIdComboBoxInLive.grid(row=1, column=4, padx=5)

        # Instruction type
        self.selectedInstructionType = StringVar()
        self.instructionTypeComboBoxInLive = ttk.Combobox(
            self.tabLiveFrame, textvariable=self.selectedInstructionType
        )
        self.instructionTypeComboBoxInLive["values"] = ["Long", "Short"]
        self.instructionTypeComboBoxInLive["state"] = "readonly"  # normal
        self.instructionTypeComboBoxInLive.current(0)
        self.instructionTypeComboBoxInLive.grid(row=1, column=5, padx=5)

        Label(self.tabLiveFrame, text="ATR Value").grid(
            row=2, column=0,  pady=10)
        Label(self.tabLiveFrame, text="Exit Profit %").grid(
            row=2, column=1,  pady=10)
        Label(self.tabLiveFrame, text="Days to Exit").grid(
            row=2, column=2,  pady=10)
        Label(self.tabLiveFrame, text="Exit API").grid(
            row=2, column=3,  pady=10)

        atrFrame = Frame(self.tabLiveFrame)
        exitProfitFrame = Frame(self.tabLiveFrame)
        daysExitFrame = Frame(self.tabLiveFrame)
        exitAPIFrame = Frame(self.tabLiveFrame)

        self.isATR = IntVar()
        self.isATRCheck = Checkbutton(
            atrFrame,
            variable=self.isATR,
            command=self.onCheckIsATR,
        )
        self.isATRCheck.pack(side=LEFT)
        self.atrValueEntry = Entry(atrFrame)
        self.atrValueEntry.insert(END, "")
        self.atrValueEntry.pack(side=LEFT)
        atrFrame.grid(row=3, column=0)

        self.isProfit = IntVar()
        self.isProfitCheck = Checkbutton(
            exitProfitFrame,
            variable=self.isProfit,
            command=self.onCheckIsProfit,
        )
        self.isProfitCheck.pack(side=LEFT)
        self.profitValueEntry = Entry(exitProfitFrame)
        self.profitValueEntry.insert(END, "")
        self.profitValueEntry.pack(side=LEFT)
        exitProfitFrame.grid(row=3, column=1)

        self.isDayExit = IntVar()
        self.isDayExitCheck = Checkbutton(
            daysExitFrame,
            variable=self.isDayExit,
            command=self.onCheckIsDayExit,
        )
        self.isDayExitCheck.pack(side=LEFT)
        self.dayExitEntry = Entry(daysExitFrame)
        self.dayExitEntry.insert(END, "")
        self.dayExitEntry.pack(side=LEFT)
        daysExitFrame.grid(row=3, column=2)

        self.isExitAPI = IntVar()
        self.isExitAPICheck = Checkbutton(
            exitAPIFrame,
            variable=self.isExitAPI,
            command=self.onCheckIsExitAPI,
        )
        self.isExitAPICheck.pack(side=LEFT)
        self.exitAPIEntry = Entry(exitAPIFrame)
        self.exitAPIEntry.insert(END, "")
        self.exitAPIEntry.pack(side=LEFT)
        exitAPIFrame.grid(row=3, column=3)

        stopExitAllBtn = Button(
            self.tabLiveFrame,
            text="Stop/Exit All",
            width=12,
            command=self.onClickStopExitAllBtn,
        )
        stopExitAllBtn.grid(row=4, column=1, pady=10)

        saveBtn = Button(
            self.tabLiveFrame,
            text="Save",
            width=12,
            command=self.onClickSaveBtn,
        )
        saveBtn.grid(row=4, column=2, pady=10)

        startBtn = Button(
            self.tabLiveFrame,
            text="Start",
            width=12,
            command=self.onClickStartBtn,
        )
        startBtn.grid(row=4, column=3, pady=10)

        self.runningStateLable = Label(
            self.tabLiveFrame, fg='#00f', text="Idle now")
        self.runningStateLable.grid(row=3, column=4, pady=10)

        Label(self.tabLiveFrame, text="Trades Entered").grid(
            row=6, column=0,  pady=2)
        Label(self.tabLiveFrame, text="Total Profit").grid(
            row=6, column=1,  pady=2)
        Label(self.tabLiveFrame, text="Profitable Trades").grid(
            row=6, column=2,  pady=2)
        Label(self.tabLiveFrame, text="Profit Factor").grid(
            row=6, column=3,  pady=2)

        self.strategyTradesTxt = Label(self.tabLiveFrame, text="0")
        self.strategyTradesTxt.grid(row=7, column=0,  pady=2)
        self.strategyTotalProfitTxt = Label(self.tabLiveFrame, text="0")
        self.strategyTotalProfitTxt.grid(row=7, column=1,  pady=2)
        self.strategyProfitableTradesTxt = Label(self.tabLiveFrame, text="0")
        self.strategyProfitableTradesTxt.grid(row=7, column=2,  pady=2)
        self.strategyProfitFactorTxt = Label(self.tabLiveFrame, text="0")
        self.strategyProfitFactorTxt.grid(row=7, column=3,  pady=2)

        frameAPIEntry = Frame(self.tabLiveFrame)
        self.currentAPIEntryTable = ttk.Treeview(
            frameAPIEntry, selectmode="browse", height=7
        )
        self.currentAPIEntryTable["columns"] = (
            "Symbol",
            "Price",
            "Time",
            "ATR(14)",
            "ROC(2)",
            "ROC(3)",
            "RS5",
            "RS10",
            "NATR(4)",
            "NATR(14)",
            "RSI(2)",
            "RSI(3)",
            "RSI(14)",
        )
        self.currentAPIEntryTable.column(
            "#0", anchor=CENTER, width=40, minwidth=20)
        self.currentAPIEntryTable.column("Symbol", anchor=CENTER, width=70)
        self.currentAPIEntryTable.column("Price", anchor=CENTER, width=70)
        self.currentAPIEntryTable.column("Time", anchor=CENTER, width=70)
        self.currentAPIEntryTable.column("ATR(14)", anchor=CENTER, width=70)
        self.currentAPIEntryTable.column("ROC(2)", anchor=CENTER, width=70)
        self.currentAPIEntryTable.column(
            "ROC(3)", anchor=CENTER, width=70)
        self.currentAPIEntryTable.column("RS5", anchor=CENTER, width=70)
        self.currentAPIEntryTable.column("RS10", anchor=CENTER, width=70)
        self.currentAPIEntryTable.column("NATR(4)", anchor=CENTER, width=70)
        self.currentAPIEntryTable.column("NATR(14)", anchor=CENTER, width=70)
        self.currentAPIEntryTable.column("RSI(2)", anchor=CENTER, width=70)
        self.currentAPIEntryTable.column(
            "RSI(3)", anchor=CENTER, width=70)
        self.currentAPIEntryTable.column("RSI(14)", anchor=CENTER, width=70)

        self.currentAPIEntryTable.heading("#0", text="ID", anchor=CENTER)
        self.currentAPIEntryTable.heading(
            "Symbol", text="Symbol", anchor=CENTER)
        self.currentAPIEntryTable.heading(
            "Price", text="Price", anchor=CENTER)
        self.currentAPIEntryTable.heading(
            "Time", text="Time", anchor=CENTER)
        self.currentAPIEntryTable.heading(
            "ATR(14)", text="ATR(14)", anchor=CENTER)
        self.currentAPIEntryTable.heading(
            "ROC(2)", text="ROC(2)", anchor=CENTER)
        self.currentAPIEntryTable.heading(
            "ROC(3)", text="ROC(3)", anchor=CENTER)
        self.currentAPIEntryTable.heading(
            "RS5", text="RS5", anchor=CENTER)
        self.currentAPIEntryTable.heading(
            "RS10", text="RS10", anchor=CENTER)
        self.currentAPIEntryTable.heading(
            "NATR(4)", text="NATR(4)", anchor=CENTER)
        self.currentAPIEntryTable.heading(
            "NATR(14)", text="NATR(14)", anchor=CENTER)
        self.currentAPIEntryTable.heading(
            "RSI(2)", text="RSI(2)", anchor=CENTER)
        self.currentAPIEntryTable.heading(
            "RSI(3)", text="RSI(3)", anchor=CENTER)
        self.currentAPIEntryTable.heading(
            "RSI(14)", text="RSI(14)", anchor=CENTER)
        self.currentAPIEntryTable.pack(side=LEFT, fill=X)

        yscrollbarForCurrentAPI = ttk.Scrollbar(
            frameAPIEntry,
            orient="vertical",
            command=self.currentAPIEntryTable.yview,
        )
        yscrollbarForCurrentAPI.pack(side=RIGHT, fill=Y)
        self.currentAPIEntryTable.configure(
            yscrollcommand=yscrollbarForCurrentAPI.set)
        frameAPIEntry.grid(row=8, column=0, columnspan=5, padx=20)
        refreshBtn = Button(
            self.tabLiveFrame,
            text="Refresh",
            width=12,
            command=self.onClickRefreshBtn,
        )
        refreshBtn.grid(row=4, column=4, pady=5)

        frameOrderList = Frame(self.tabLiveFrame)
        self.orderTreeView = ttk.Treeview(
            frameOrderList, selectmode="browse", height=10
        )
        self.orderTreeView["columns"] = (
            "Symbol",
            # "Strategy",
            # "Planned Exit",
            "Account",
            "Entry Order",
            "Exit Order",
            # "Profit Target1",
            "Entry Date",
            "Entry Price",
            "Shares",
            "Exit Target",
            "Exit Date",
            "Exit Price",
            "Entry Amount",
            "Exit Amount",
            "Actual Profit",
            "Actual Exit",
        )
        self.orderTreeView.column(
            "#0", anchor=CENTER, width=40, minwidth=20)
        self.orderTreeView.column("Symbol", anchor=CENTER, width=70)
        # self.orderTreeView.column("Strategy", anchor=CENTER, width=70)
        # self.orderTreeView.column(
        #     "Planned Exit", anchor=CENTER, width=70)
        self.orderTreeView.column("Account", anchor=CENTER, width=70)
        self.orderTreeView.column("Entry Order", anchor=CENTER, width=80)
        self.orderTreeView.column("Exit Order", anchor=CENTER, width=80)
        # self.orderTreeView.column("Profit Target1", anchor=CENTER, width=70)
        self.orderTreeView.column("Entry Date", anchor=CENTER, width=100)
        self.orderTreeView.column("Entry Price", anchor=CENTER, width=70)
        self.orderTreeView.column("Shares", anchor=CENTER, width=70)
        self.orderTreeView.column("Exit Target", anchor=CENTER, width=70)
        self.orderTreeView.column("Exit Date", anchor=CENTER, width=100)
        self.orderTreeView.column("Exit Price", anchor=CENTER, width=70)
        self.orderTreeView.column("Entry Amount", anchor=CENTER, width=70)
        self.orderTreeView.column("Exit Amount", anchor=CENTER, width=70)
        self.orderTreeView.column("Actual Profit", anchor=CENTER, width=70)
        self.orderTreeView.column(
            "Actual Exit", anchor=CENTER, width=70)

        self.orderTreeView.heading("#0", text="ID", anchor=CENTER)
        self.orderTreeView.heading(
            "Symbol", text="Symbol", anchor=CENTER)
        # self.orderTreeView.heading(
        #     "Strategy", text="Strategy", anchor=CENTER)
        # self.orderTreeView.heading(
        #     "Planned Exit", text="Planned Exit", anchor=CENTER)
        self.orderTreeView.heading(
            "Account", text="Account", anchor=CENTER)
        self.orderTreeView.heading(
            "Entry Order", text="Entry Order", anchor=CENTER)
        self.orderTreeView.heading(
            "Exit Order", text="Exit Order", anchor=CENTER)
        # self.orderTreeView.heading(
        #     "Profit Target1", text="Profit Target1", anchor=CENTER)
        self.orderTreeView.heading(
            "Entry Date", text="Entry Date", anchor=CENTER)
        self.orderTreeView.heading(
            "Entry Price", text="Entry Price", anchor=CENTER)
        self.orderTreeView.heading(
            "Shares", text="Shares", anchor=CENTER)
        self.orderTreeView.heading(
            "Exit Target", text="Exit Target", anchor=CENTER)
        self.orderTreeView.heading(
            "Exit Date", text="Exit Date", anchor=CENTER)
        self.orderTreeView.heading(
            "Exit Price", text="Exit Price", anchor=CENTER)
        self.orderTreeView.heading(
            "Entry Amount", text="Entry Amount", anchor=CENTER)
        self.orderTreeView.heading(
            "Exit Amount", text="Exit Amount", anchor=CENTER)
        self.orderTreeView.heading(
            "Actual Profit", text="Actual Profit", anchor=CENTER)
        self.orderTreeView.heading(
            "Actual Exit", text="Actual Exit", anchor=CENTER)

        self.orderTreeView.pack(side=LEFT, fill=X)

        yscrollbarForOrderList = ttk.Scrollbar(
            frameOrderList,
            orient="vertical",
            command=self.orderTreeView.yview,
        )
        yscrollbarForOrderList.pack(side=RIGHT, fill=Y)
        self.orderTreeView.configure(
            yscrollcommand=yscrollbarForOrderList.set)
        frameOrderList.grid(row=9, column=0, columnspan=11, padx=20)


class Strategy:
    def __init__(self):
        self.formula1 = ""
        self.formula2 = ""
        self.formula3 = ""
        self.limit1 = ""
        self.limit2 = ""
        self.limit3 = ""
        self.sort1 = "Increase"
        self.sort2 = "Increase"
        self.sort3 = "Increase"
        self.tradeStepTime = ""
        self.tradeDuration = ""
        self.scaling = "10"
        self.startAmount = ""
        self.rebalance = "None"
        self.profitTarget = ""
        self.selectedStrategyFromComboBox = ""
        self.txtResult = ""
        self.tradeLogArray = []


if __name__ == "__main__":
    root = Root()
    root.protocol("WM_DELETE_WINDOW", root.on_closing)
    root.mainloop()
