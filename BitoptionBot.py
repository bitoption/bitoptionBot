#!/usr/bin/env python
########################################################################
##	Name: BitoptionBot.py
##	Description:This is a script to do back testing using Black-Scholes.
##                As well can direct call and put posts for a defined
##                client on bitoption.org.
##                The idea is to use the bot to make a rough predictions
##                and then use those predictions to make calls and puts.
##
##
##	Author: Peter and Ryan
##  URL:    https://bitoption.org
##  Email:  admin@bitoption.com
##          ryan@bitoption.com
##  Date: July,2011
##
########################################################################
import pycurl, json, urllib, logging, re
import pickle
from scipy.stats import norm
import numpy as np
from time import time, ctime, mktime, clock
from datetime import datetime, date, timedelta
import bisect
from collections import defaultdict
from pysqlite2 import dbapi2 as sqlite3
from random import random, choice, uniform
import sys
import cProfile

#SQL settings to attempt to make inserts/selects faster
conn = sqlite3.connect(':memory:')
c = conn.cursor()
c.execute('PRAGMA temp_store=MEMORY;')
c.execute('PRAGMA journal_mode=MEMORY;')
c.execute ("PRAGMA synchronous=OFF")
conn.isolation_level="EXCLUSIVE"

#Create SQL table to store volatility. Probably not necessary, but nice to have a database full of volatilities!
c.execute('CREATE TABLE volatility (startperiod integer, endperiod integer, value real);')

class Client:
    ''' '''
    def __init__(self, username="", password=""):
        ''' '''
        self.username = username
        self.password = password
        self.buff = ""
        self.token = ""
        self.balances = ''
        self._xsrf = ''
        self.base_url = "https://bitoption.org"
        self.login_url = "/login"
        self.timeout = 100
        self.curl = pycurl.Curl()
        self.curl.setopt(pycurl.POST, 1)
        self.curl.setopt(pycurl.COOKIEJAR, "")
        #self.curl.setopt(pycurl.)
        #self.curl.setopt(pycurl.FOLLOWLOCATION, 1)
        #self.curl.setopt(pycurl.PROXY,'localhost')
        #self.curl.setopt(pycurl.PROXYPORT,8888)
        #self.curl.setopt(pycurl.SSL_VERIFYPEER,0)
        self.curl.setopt(pycurl.VERBOSE, 0)
        self.curl.setopt(pycurl.TIMEOUT, self.timeout)
        #self.curl.setopt(pycurl.HTTPHEADER, ['X-Requested-With: XMLHttpRequest'])
        #self.curl.setopt(pycurl.HTTPHEADER, ['Expect: '])
        #self.curl.setopt(pycurl.COOKIEJAR,'/tmp/pycurlcookies.txt')
        #self.curl.setopt(pycurl.USERAGENT,'Mozilla/5.0 (Windows; U; MSIE 9.0; WIndows NT 9.0; en-US)')

        #self.log = log
        self.token = self.login()

    def perform(self, path, params,method="POST",referer=None):
        ''' '''
        self.buff = ""
        #self.curl.setopt(pycurl.VERBOSE, 1)
        if method == "GET":
                self.curl.setopt(pycurl.POST,0)
        else:
                self.curl.setopt(pycurl.POST,1)
                params = params.items()
                self.curl.setopt(pycurl.HTTPPOST, params)
        
        self.curl.setopt(pycurl.WRITEFUNCTION, self._write)
        if referer:
                self.curl.setopt(pycurl.REFERER,referer)
        url = "%s%s" % (self.base_url, path)
        self.curl.setopt(pycurl.URL, url)

        self.curl.perform()
        status = self.curl.getinfo(pycurl.HTTP_CODE)
        if status == "OK" or status == 200 or status == 302:
            return self.buff
        else:
            raise ServerError(self.buff)

    def _write(self, x):
        ''' '''
        self.buff += x
    
    def login(self):
        ''' '''
        log.debug("---Entering login()")
        params = {'name':self.username,'password': self.password}
        log.debug(self.base_url)
        # Send a get out to / to populate our xsrf token
        self.perform("",{},method="GET")
        cookies = self.curl.getinfo(pycurl.INFO_COOKIELIST)
        _xsrf = [cookie.split("\t")[6] for cookie in cookies if cookie.split("\t")[5] == "_xsrf"][0]
        log.debug("_xsrf = "+_xsrf.encode('ascii'))
        params["_xsrf"] = _xsrf
        self._xsrf = _xsrf
        # From now on, we're posting to get token info.
        loginInfo = self.perform(self.login_url,params)
        loginInfo = json.loads(loginInfo)
        log.debug("login info: ")
        log.debug(loginInfo)
        # The encode call is here to change token value to a string not a unicode value. Be careful with this,
        # it assumes that there are no special characters in the unicode value.
        return loginInfo["token"].encode('ASCII', 'ignore')

    def accountBalance(self):
        ''' '''
        log.debug("---Entering accountBalance()")
        acct_url = "/accountBalance"
        params = {'token': self.token}
        accBal = self.perform(acct_url,params, method='GET')
        accBal = json.loads(accBal)
        log.info('   STRING CONVERSION TO FLOAT')
        #There is a standard of fixed point arithmetic (6 digits past the decimal), hence the INFO log.
        self.balances = dict([[x.encode('ascii'),float(y.encode('ascii'))] for x,y in accBal["balances"]])
        log.debug("   Account Balances type: %s",str(type(self.balances)))
        log.debug("   Account Balance data:")
        log.debug(self.balances)
        return None
    
    def write(self,type,date,strike,ask,num):
        '''
            basic function to write a call/put option
        '''
        log.debug("---Entering write()")
        write_url = "/write"
        params = {'token':self.token,'type':type,'date':date,'strike':strike,'ask':ask,'num':num}
        writeInfo = self.perform(write_url, params)
        writeInfo = json.loads(writeInfo)
        log.info('   Finished Write: %s' % (writeInfo))
        
        #check for fails
        if writeInfo['status']=='failed':
            print " Write failed: %s" % (writeInfo['message'])
        
        return None
        
    def bid(self,type,strikedate,strike,bid,num):
        '''
            basic function to bid on a call/put option
        '''
        log.debug("---Entering write()")
        bid_url = "/bid"
        params = {'token':self.token,'type':type,'strikedate':strikedate,'strike':strike,'bid':bid,'num':num}
        bidInfo = self.perform(bid_url, params)
        bidInfo = json.loads(bidInfo)
        log.info('   Finished Bid: %s' % (bidInfo))
        
        #check for fails
        if bidInfo['status']=='failed':
            print " Bid failed: %s" % (bidInfo['message'])
        
        return None

    def tokenTests(self,debug=True):
        ''' Just a few tests on retrieving info using self.token '''
        log.debug("---Entering tokenTests()")

        #accountbalance
        acct_url = "/accountBalance"
        #params = {'token': self.token, '_xsrf': self._xsrf}
        params = {'token': self.token}
        log.debug("   params: %s" % (params))
        accBal = self.perform(acct_url, params,method="GET")
        log.debug("   Account Balance = %s" % (accBal))
        return None
        

class BackTester:
    '''
        General set of tools to help with trading!
    '''
    def __init__(self,startDate=int(time())-(60*60*24*14),endDate=int(time()),volatilityWindow=60*60*24*10,dataSource=0):
        '''
            User can define duration of back testing using startDate and
            endDate. The default starts 2 weeks in the past from the 
            current date, using a 10-day vcolatility estimate window and 
            downloading all data.
        '''
        self.dataSymbol = 'mtgoxUSD'
        self.mtgoxLatest = ""
        self.historicalData = []
        self.offer = 0.1
        self.bid = 0.1
        self.blackScholes_rate= 0.0  #interest per second please

        # Way to choose data source:
        #   0: downloads data for current timeinverval (start-volatinityWindow to endDate). This will be faster than pickleing when the time interval is smaller. 
        #   1: Downloads ALL mt. gox trade history upto the given endDate. This will take WAY TOO LONG and probably unnecessary!
        #   2: Uses predownloaded pickle of trade history. Takes a while to unpickle and the endDate is less than the current time, but it's there is you need it :-)
        if dataSource == 0:
            log.debug('   backTester.init() Downloading data for time %s to %s' % (str(datetime.fromtimestamp(startDate-volatilityWindow)),
                                                                                    str(datetime.fromtimestamp(endDate))))
            self.historicalData = self.btcTradeHistory(self.dataSymbol,startDate-volatilityWindow,endDate)
        elif dataSource == 1:
            log.debug('   backTester.init() Downloading ALL Trade History & saving to pickle, this will take some time!')
            pkl_file = open('tradehistory.pickle','w')
            pickle.dump(self.btcTradeHistory(self.dataSymbol,0,endDate),pkl_file)
            self.historicalData = pickle.load(pkl_file)
            pkl_file.close()
        elif dataSource == 2:
            log.debug('   backTester.init() Unpickleing predownloaded data, this will only take a bit!')
            pkl_file=open("tradehistory.pickle","r")
            self.historicalData = pickle.load(pkl_file)
            pkl_file.close()

        #This is an array to hold integer values for the dates
        self.historicalIndex= [int(f[0]) for f in self.historicalData]


    def getPriorIndexAtSecond(self,second):
        '''
            Pretty straight-forward. You give a date in the past (sec) and 
            this returns a Mt. Gox trade price INDEX closest to that second. 
        '''
        bisect_result = max(bisect.bisect_left(self.historicalIndex,second) -1,0)
 
        log.debug ("   getPriorIndexAtSecond() Second: %s, index: %s"% (second, bisect_result))
        return bisect_result

    def volatilityForPeriod(self,start,end,data):
        ''' 
            beware start = "1; delete from options where 1 = 1; 
            select * from volatility where "
        '''
        sql = "select value from volatility where startperiod = %s and endperiod = %s" % (start,end)
        c.execute(sql)
        value = c.fetchone()
        if value is not None:
            return value[0]
        else:
            # get appropriate data , call volatility_simpEstimate with data, store the result
            # Are we SURE we don't take one extra second at the end?

            data = self.historicalData[max(self.getPriorIndexAtSecond(start),0):self.getPriorIndexAtSecond(end)+1]
            log.debug("   volatilityForPeriod() Time slice is: %s" % (len(data)))
            value = self.volatility_simpEstimate(data)
            sql = "insert into volatility (startperiod,endperiod,value) values (?,?,?)" 
            c.execute(sql,(start,end,value))
            conn.commit()
            return value

    def btcTradeHistory(self,symbol, start, end):
        '''
            Grabs trade history from bitcoincharts.com. Inputs are in 
            UNIXTIME, and a list of valid symbols can be found at:
                http://bitcoincharts.com/t/markets.json
            The default start amd end times are pulled from the current 
            assignments.
        '''

        #probably a better way to do this:
        #if symbol is None: symbol=self.dataSymbol
        #if start is None: start=self.startDate
        #if end is None: end=self.endDate

        log.debug("---Entering btcTradeHistory()")
        trade_url = 'http://bitcoincharts.com/t/trades.csv?'
        params = {'symbol':symbol, 'start': start, 'end': end}
        params = urllib.urlencode(params)
        log.debug('   params = %s',params)
        data = urllib.urlopen(trade_url + '%s' %  params)
        return [re.split(',',entry) for entry in re.split('\n',data.read())]


    def volatility_simpEstimate(self, data=None, period="seconds"):
        '''
            This is a simple volatility estimate from historical data
            tradeData is a list:
            [['time1', 'price1'],['time2','price2'], ...]

            This estimate also does something special with the data during the Mt Gox
            flash crash... it removes it! The dates removed are from June 19th 2011
            (1308459600) to July 1st 2011 (1309496400).
        '''
        
        log.debug('---Entering volatility()')

        #mt gox flash crash
        crashStart = 1308459600
        crashEnd = 1309496400

        if data is None: data=self.tradeData

        vol = {'annual':0.0, 'daily':0.0, 'error':0.0}

        base_second = int(data[0][0])
        num_seconds = int(data[-1][0]) - base_second
        stockNum = len(data)
        log.debug('   Zeroing array ')

        logReturn = np.zeros(num_seconds,dtype=np.float32)
        last_entry = float(data[0][1])
        log.debug('   Beginning the fill.. %s slices ' % logReturn.shape )

        for entry in data:
            if not((int(entry[0]) > crashStart) and (int(entry[0]) < crashEnd)):
                logReturn[base_second - int(entry[0])] = np.log(float(entry[1])/last_entry)
                last_entry = float(entry[1])

        log.debug('   Begin standDev calc')
        standDev = np.std(logReturn)

        vol['seconds'] = standDev
        vol['annual'] = standDev * np.sqrt(60*60*24*365)
        vol['daily'] = standDev * np.sqrt(60*60*24)
        vol['error'] = vol['annual']/float(2*stockNum)


        log.info('   Volatility Estimate for Date %s: %s' % (date.fromtimestamp(int(data[0][0])),vol[period]))
        
        return vol[period]

    #black-scholes related functions
    def get_call_price(self, seconds_to_expiration, price, strikePrice, vol, rate=None, offer=None, bid=None):
        '''
            Straight-forward call calculation using Black-Scholes Formula
        '''
        
        if rate is None: rate=self.blackScholes_rate
        if offer is None: offer=self.offer
        if bid is None: bid=self.bid

        call = {'fair':0.0,'bid':0.0,'offer':0.0}

        d1 = ((np.log(price/strikePrice) + (rate + (vol**2)/2.0)*seconds_to_expiration))/(vol*np.sqrt(seconds_to_expiration))
        d2 = ((np.log(price/strikePrice) + (rate - (vol**2)/2.0)*seconds_to_expiration))/(vol*np.sqrt(seconds_to_expiration))
        call['fair'] = (price*norm.cdf(d1)) - (strikePrice*np.exp(-rate*seconds_to_expiration)*norm.cdf(d2))
        call['bid'] = price - price*bid
        call['offer'] = price + price*offer

        return call

    def get_put_price(self, seconds_to_expiration, price, strikePrice, vol, rate=None, offer=None, bid=None):
        '''
            Straight-forward put calculation using Black-Scholes Formula
        '''
        
        if rate is None: rate=self.blackScholes_rate
        if offer is None: offer=self.offer
        if bid is None: bid=self.bid

        put = {'fair':0.0,'bid':0.0,'offer':0.0}

        d1 = ((np.log(price/strikePrice) + (rate + (vol**2)/2.0)*seconds_to_expiration))/(vol*np.sqrt(seconds_to_expiration))
        d2 = ((np.log(price/strikePrice) + (rate - (vol**2)/2.0)*seconds_to_expiration))/(vol*np.sqrt(seconds_to_expiration))
        put['fair'] = (strikePrice*np.exp(-rate*seconds_to_expiration)*norm.cdf(-d2)) - (price*norm.cdf(-d1))
        put['bid'] = price + price*bid
        put['offer'] = price - price*offer

        return put

    def priceAtSecond(self,second):
        '''
            You give the second, it returns the Mt. Gox price closest to
            that second.
        '''
        
        index = max(bisect.bisect_left(self.historicalIndex,second)-1,0)
        return float(self.historicalData[index][1])

    def get_expirationTime(self,testTime):
        '''
            Function to give the upcomming expiration date, the nearest
            Thur. at 0:0:0 GMT
        '''
        currTime = date.fromtimestamp(testTime)
        timeDelta = (4-currTime.isoweekday()) % 7
        future = currTime + timedelta(days = timeDelta)
        #convert future to timestamp and return
        return int(mktime(future.timetuple()))
        
    def getPossibleStrikes(self):
        '''
            Returns an array of resonable strike prices.
        '''
        return [0.01,0.05,0.1,0.25,0.5,1.0,1.5,2.0,2.5,5.0,7.5,10.0,12.5,15.0,17.5,20.0,25.0,30.0,35.0,40.0,45.0,50.0,75.0,100.0]

    def convertPriceToData(self,price):
        '''
        '''
        return int(round(float(price)*10000))

    def convertDataToPrice(self,data):
        '''
        '''
        return round(float(data/10000.0),4)
    
    def run(self,startDate,endDate,timeInterval,volatilityWindow,callRate=0.5,putRate=0.5):
        '''
            This is the real meat of the back tester. User provides time
            interval dates. Call/Put rates correspond to how often someone
            buys your call/put: e.g. 0.5 means 50% of the time and 0.01 
            would mean 1% of the time.
            Returned dicts hold all options contracts, the capital
            requirements (at purchase) for each party, and the total 
            number of buyer and seller contracts.
        '''

        totalContracts = {'buy':0,'sell':0}
        weekCounter = 0
        fiveMinuteCounter = 0
        capitalReqs = defaultdict(lambda: {'mm':{'usd':0.0,'btc':0.0},'spec':{'usd':0.0,'btc':0.0}})
        #Inception dict! Used to hold ALL the options information. Leo DiCaprio:"We have to go deeper to store that list of dicts!"
        #   options[expiration date of contract][buyer: marketmaker or speculator][contract type: call or put][strike price] = [{transaction price, boolean:used as credit}] 
        options = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))


        for simTime in range(startDate,endDate,timeInterval):
            
            #use this to show simulation progress
            temp = round(100.0*float(endDate - simTime)/float(endDate-startDate),4)
            str1 = 'Percent to Finish: %.4f ' % temp
            sys.stderr.write(str1+ '\r')

            #update volatility every week
            if weekCounter == 604800 or weekCounter == 0:
                tradeData = self.historicalData[max(self.getPriorIndexAtSecond(startDate-volatilityWindow),0):self.getPriorIndexAtSecond(startDate)+1]
                volatility = self.volatilityForPeriod(startDate-volatilityWindow,startDate-1,tradeData)
                weekCounter = 0

            weekCounter += timeInterval

            #update my strikePrices every 5 minutes
            if fiveMinuteCounter == 300 or fiveMinuteCounter == 0:
                price = float(self.priceAtSecond(simTime))
                callStrikePrice = choice([strike for strike in self.getPossibleStrikes() if strike >= .5*price and strike <= 2.0*price])
                putStrikePrice = choice([strike for strike in self.getPossibleStrikes() if strike >= .5*price and strike <= 2.0*price])

                #select random time between start and end date and then find nearest expirationTime
                expiration = self.get_expirationTime(uniform(startDate,endDate))
                #determine time to expiration in years
                deltaSeconds= float(expiration - simTime)
                callPrice = self.get_call_price(deltaSeconds,price,callStrikePrice,volatility)
                putPrice = self.get_put_price(deltaSeconds,price,putStrikePrice,volatility)
                fiveMinuteCounter = 0

            fiveMinuteCounter += timeInterval

            #someone might buy and sell every timeInterval. If the price is less than 0.01, then it is not worth it!
            if callPrice > 0.01:
                if random() < callRate:
                    mm_total_type = "buy"
                    seller = "mm"
                    seller_long = "mm"
                    buyer_long = "spec"
                    buyer = "spec"
                    pricetype = "offer"
                else:
                    mm_total_type = "sell"
                    seller = "spec"
                    seller_long = "spec"
                    buyer_long = "mm"
                    buyer = "mm"
                    pricetype = "bid"
                contractType = 'call'

                # buy a call at offer -- do we use a call contract or BTC as a guarantee?
                totalContracts[mm_total_type] += 1

                # do we have a call contract we can use? Something the seller previously bought?
                strikelist = options[expiration][buyer][contractType].keys()
                # strikelist has all the existing strikes
                strikelist = [strike for strike in strikelist if strike <= callPrice[pricetype]]
                if len(strikelist) >= 1:
                    for item in range(0,len(options[expiration][buyer][contractType][strikelist[-1]])):
                        if options[expiration][buyer][contractType][strikelist[-1]][item]['used_as_credit_p']== False:
                            options[expiration][buyer][contractType][strikelist[-1]][item]['used_as_credit_p'] = True
                            break
                        else:
                            capitalReqs[str(expiration)][seller_long]['btc']+=1
                else:
                    capitalReqs[str(expiration)][seller_long]['btc']+=1

                options[expiration][buyer][contractType][callStrikePrice].append({"trans_price":callPrice[pricetype],'used_as_credit_p':False})

                # speculator needs cash, mm needs btc
                #grab contracts in current weekly period that have strikes lower than current stike
                capitalReqs[str(expiration)][buyer_long]['usd']+=round(callPrice[pricetype],4)
                capitalReqs[str(expiration)][seller_long]['usd']-=round(callPrice[pricetype],4)


            if putPrice > 0.01:
                    if random() < putRate:
                        mm_total_type = "buy"
                        seller = "mm"
                        seller_long = "mm"
                        buyer_long = "spec"
                        buyer = "spec"
                        pricetype = "offer"
                    else:
                        mm_total_type = "sell"
                        seller = "spec"
                        seller_long = "spec"
                        buyer_long = "mm"
                        buyer = "mm"
                        pricetype = "bid"
                    contractType = 'put'

                    # buy a put at offer -- do we use a put contract or USD as a guarantee?
                    totalContracts[mm_total_type] += 1

                    # do we have a call contract we can use? Something the seller previously bought?
                    strikelist = options[expiration][buyer][contractType].keys()
                    # strikelist has all the existing strikes
                    strikelist = [strike for strike in strikelist if strike >= putPrice[pricetype]]
                    if len(strikelist) >= 1:
                        for item in range(0,len(options[expiration][buyer][contractType][strikelist[-1]])):
                            if options[expiration][buyer][contractType][strikelist[-1]][item]['used_as_credit_p']== False:
                                options[expiration][buyer][contractType][strikelist[-1]][item]['used_as_credit_p'] = True
                                break
                            else:
                                capitalReqs[str(expiration)][seller_long]['usd']+=putStrikePrice
                    else:
                        capitalReqs[str(expiration)][seller_long]['usd']+=putStrikePrice
                    

                    options[expiration][buyer][contractType][putStrikePrice].append({"trans_price":putPrice[pricetype],'used_as_credit_p':False})

                    # speculator needs cash, mm needs btc
                    #grab contracts in current weekly period that have strikes lower than current stike
                    capitalReqs[str(expiration)][buyer_long]['usd']+=round(putPrice[pricetype],4)
                    capitalReqs[str(expiration)][seller_long]['usd']-=round(putPrice[pricetype],4)
        log.info('   Finished!')
        return options, capitalReqs, totalContracts

    def getResults(self,options,capitalReqs,totalContracts):
        '''
            Called after run(). This will take the output of run() and 
            print is out as an easy to parse CSV. So in Linux, one would
            run as:
                $python bitoptionBot.py > simulationResults.csv
                
            All results are then stored in simulationResults.csv
        '''
        log.debug("---Entering getResults()")
        log.debug("   Capital Reqs: %s" % (capitalReqs))
        
        excCapitalReqs = defaultdict(lambda: {'mm':{'usd':0.0,'btc':0.0},'spec':{'usd':0.0,'btc':0.0}})
        itmByExpiration = defaultdict(lambda: {'mm':{'calls':0,'puts':0},'spec':{'calls':0,'puts':0}})
        
        #TODO: The output for this looks worng needs some more work!
        print "Expiration,(unix),MM Earnings,Spec Earnings,MM USD,MM BTC,Spec USD,Spec BTC,itm mm put, itm mm call, spec mm put, spec mm call, exc mm cap btc, exc mm cap usd, exc spec mm cap btc, exc spec mm cap usd"
        #print "-------------------------------------------------------------------------------------------------------------------------------------"
        optionsSorted = sorted(options)
        for expiration in optionsSorted:
            weekly_gain = defaultdict(float)

            expiration_price = self.priceAtSecond(int(expiration))
            #print "---calls---"
            for party in options[expiration].keys():
                if party == "mm":
                    opposite = "spec"
                else:
                    opposite = "mm"
                for contractType in ('call','put'):
                    for strike in options[expiration][party][contractType].keys():
                            #print call
                            # list of options at this strike
                            for option in options[expiration][party][contractType][strike]:
                                weekly_gain[party] += option['trans_price']
                                weekly_gain[opposite] -= option['trans_price']
                                #print "%s, %s" % (mm_gain,speculator_gain)
                                
                                if strike < expiration_price and contractType == "call":
                                    #call is in the money
                                    weekly_gain[party] -= expiration_price - strike
                                    weekly_gain[opposite] += expiration_price - strike
                                    itmByExpiration[expiration][party]['calls']+=1
                                    excCapitalReqs[expiration][party]['btc']+=1
                                    #print "%s, %s" % (mm_gain,speculator_gain)
                                elif strike > expiration_price and contractType == "put":
                                    weekly_gain[party] -= -expiration_price + strike
                                    weekly_gain[opposite] += -expiration_price + strike
                                    itmByExpiration[expiration][party]['puts']+=1
                                    excCapitalReqs[expiration][party]['usd']+=strike
                                    
           
            print"{0:s},({1:d}),{2:f},{3:f},{4:f},{5:f},{6:f},{7:f},{8:f},{9:f},{10:f},{11:f},{12:f},{13:f},{14:f},{15:f},{16:f}".format(str(date.fromtimestamp(int(expiration))),int(expiration),
                        weekly_gain['mm'],weekly_gain['spec'],
                        capitalReqs[str(expiration)]['mm']['usd'],
                        capitalReqs[str(expiration)]['mm']['btc'],
                        capitalReqs[str(expiration)]['spec']['usd'],
                        capitalReqs[str(expiration)]['spec']['btc'],
                        expiration_price,
                        itmByExpiration[expiration]['mm']['puts'],
                        itmByExpiration[expiration]['mm']['calls'],
                        itmByExpiration[expiration]['spec']['puts'],
                        itmByExpiration[expiration]['spec']['calls'],
                        excCapitalReqs[expiration]['mm']['btc'],
                        excCapitalReqs[expiration]['mm']['usd'],
                        excCapitalReqs[expiration]['spec']['btc'],
                        excCapitalReqs[expiration]['spec']['usd'])


def main():
    '''
        Here are some code testing-snippets/examples for the Client and
        BackTester classes.
    '''
    
    log.info("----BEGIN CLIENT TESTS----")
    #read username and pass from userinfo file 
    f = open('userinfo','r')
    userinfo = [entry for entry in re.split('\n',f.read())]
    testClient = Client(userinfo[0], userinfo[1])
    #check if login got the right info
    log.info('   client token = %s', testClient.token)
    #test for account balance
    testClient.accountBalance()
    
    log.info("----BEGIN BACK TESTER TESTS----")
    #define some important variables
    callRate = 0.5 #if set to .5, means there is a 50/50 change someone will buy a call
    putRate = 0.5 # same as above for puts
    start = 1283749201              #09 / 06 / 2010 @ 0:0:0 EST
    #end = int(time())-60*60*24*14 #A week prior to code execution
    end = start + 60*60*24*7
    simTimeInterval = 60 #seconds
    volatilityWindow = 60*60*24*10 #seconds

    #instantiate backTester
    backTest = BackTester(start,end,volatilityWindow)
    
    #start stepping through time
    log.info("   Start Model")
    str1 = '      start time: {0:1d} unix, {1:3s} '.format(start, str(datetime.fromtimestamp(start)))
    log.info(str1)
    str2 = '      end time  : {0:1d} unix, {1:3s} '.format(end, str(datetime.fromtimestamp(end)))
    log.info(str2)

    [options, capitalReqs, totalContracts] = backTest.run(start,end,simTimeInterval,volatilityWindow,callRate,putRate)

    #do some post-processing
    backTest.getResults(options,capitalReqs,totalContracts)

    log.info("---Model Summary---")
    log.info("   -Model Sim Time :    %s sec", str(end-start))
    log.info("   -Model Step Size:    %s sec", str(simTimeInterval))
    log.info("   -Volatility window:  %s sec", str(volatilityWindow))
    log.info("   -Call Rate:       %s", str(callRate))
    log.info("   -Put Rate :       %s", str(putRate))
    log.info("   -Offer Percent:   %s", str(backTest.offer*100.0))
    log.info("   -Bid Percent:     %s", str(backTest.bid*100.0))
    log.info("   -Total Contracts:")
    str1 = "      Buy: {0:d}  Sell: {1:d}".format(totalContracts['buy'], totalContracts['sell'])
    log.info(str1)

logging.basicConfig()
log = logging.getLogger("BitOption Bot")


if __name__ == "__main__":
    log.setLevel(logging.INFO)
    #cProfile.run('main()')
    main()

