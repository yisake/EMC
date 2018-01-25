#!/usr/bin/env python
#
# by Vincent.Liao@emc.com

import pyodbc
import datetime
import os
import threading
import Queue
import unicodedata, re
import getopt, sys
sys.path.insert(0, 'C:/Python27/Lib/xlwt')
import xlwt
import urllib2
import subprocess
import xml.etree.ElementTree as ET
import htmlentitydefs

ardb_drv_string = 'DRIVER={AR System ODBC Driver}'
ardb_conn_string = 'ODBC;DSN=ARSYSTEM2.isus.emc.com;ARServer=ARSYSTEM2.isus.emc.com;UID=dimsreport;PWD=report;ARAuthentication=;ARUseUnderscores=1;ARNameReplace=1;SERVER=NotTheServer'

accdb_drv_string = 'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)}'
accdb_name = 'C:\\Users\\liaov1\\ar_hist.accdb'
accdb_conn_prefix = 'ODBC;DBQ='

excel_file_name = 'C:\\Users\\liaov1\\ar_hist.xls'

ar_triage_member = ['liaov1', 'congh', 'dengb', 'gaoj3', 'jiangl6', 'liangs4', 'longa4', 'luoy', 'mam17', 'mengs', 'qianm', 'wangc20', 'xiongk', 'zhangf17', 'zhangs19']
team_a_member = ['liaov1', 'longa4', 'huangd5', 'huangc11', 'lig15', 'xuw10']

MAX_WORKERS = 30
vdm_triage_str = 'NAS Servers (VDM)'
max_str_len = 32700
control_chars_range = range(0, 9) + range(11, 32) + range(127, 256)

ar_hist_start = datetime.datetime(2014, 1, 1, 0, 0, 0)
ar_hist_end = datetime.datetime.now()

issue_trail_tabname = 'EMC_Issue_Audit_join'
issue_trail_fields = ['Entry_Id', 'From_Value', 'To_Value', 'Create_Date', 'Request_Id']
# issue_trail_filter = 'Entry_Id=650559'
# issue_trail_filter = 'Entry_Id=\'000000000650559\' AND (From_Value=\'%s\' OR To_Value=\'%s\')' %(vdm_triage_str, vdm_triage_str)
# issue_trail_filter = 'Entry_Id=\'000000000702061\' AND (From_Value=\'%s\' OR To_Value=\'%s\')' %(vdm_triage_str, vdm_triage_str)
# issue_trail_filter2 = 'Entry_Id=702061 AND (From_Value=\'%s\' OR To_Value=\'%s\')' %(vdm_triage_str, vdm_triage_str)
issue_trail_filter = 'From_Value=\'%s\' OR To_Value=\'%s\'' %(vdm_triage_str, vdm_triage_str)
issue_trail_filter2 = 'From_Value=\'%s\' OR To_Value=\'%s\'' %(vdm_triage_str, vdm_triage_str)

note_usr_filter = ['automatos']

ar_trail_tabname = 'EMC_SHARE_Audit'
ar_trail_fields = ['Request_Id', 'From_Value', 'To_Value', 'Last_Modified_By', 'Modified_Date']
ar_trail_filter_key = 'Request_Id'

ar_note_tabname = 'EMC_Issue_Notes_Join'
ar_note_fields = ['Entry_Id', 'Note_Details', 'Note_Create_Date', 'Created_By']
ar_note_filter_key = 'Entry_Id'

ar_issue_tabname = 'EMC_Issue_Tracking'
ar_issue_fields = ['Entry_Id', 'Assigned_To', 'Create_Date',
    'Full_Details', 'Product', 'Product_Area', 'Product_Release', 
    'Root_Cause', 'Root_Cause_Analysis_Notes', 'Status', 'Summary',
    'Support_Materials', 'Prime_Bug_Id']
ar_issue_filter_key = 'Entry_Id'

def usage():
    print 'This tool analysis ARs: \n\
\t(1) grab all AR data from AR Remedy system database \n\
\t(2) export AR data to local accdb database \n\
\t(3) export AR data to Solr search engine \n\
\t(4) analysis AR, for example, audit trail, notes merged,... \n\n\
Options are: \n\
\t-h --help:     display this usage \n\
\t-a --action:   define actions {ar-crawl|export2excel|export2solr} \n\
\t-D --local-db: local database name (.accdb) \n\
\t-E --excel:    export excel file name \n\
\t-L --log:      log file name \n\
    '

""" Utilities """
log_lock = threading.Lock()
log_file_name = None
log_file = None
LOG_ERR    = 1
LOG_WARN   = 2
LOG_FUNC   = 3
LOG_DETAIL = 4
LOG_DEBUG  = 5
log_lvl = LOG_FUNC
MAX_LOG_SIZ = 256
def log(msg, lvl=LOG_FUNC):
    if lvl <= log_lvl:
        log_lock.acquire()
        if log_file != None:
            log_file.write('%s\n' %msg[:MAX_LOG_SIZ])
        print msg[:MAX_LOG_SIZ]
        log_lock.release()

def time_between(t, start, end):
    # convert '2014-05-14 14:30:22' to datetime object
    if isinstance(t, basestring):
        t = datetime.datetime.strptime(t, '%Y-%m-%d %H:%M:%S')
    if isinstance(start, basestring):
        start = datetime.datetime.strptime(start, '%Y-%m-%d %H:%M:%S')
    if isinstance(end, basestring):
        end = datetime.datetime.strptime(end, '%Y-%m-%d %H:%M:%S')

    if t > start and end > t:
        return True
    else:
        return False

def same_day(t1, t2):
    if isinstance(t1, basestring):
        t1 = datetime.datetime.strptime(t1, '%Y-%m-%d %H:%M:%S')
    if isinstance(t2, basestring):
        t2 = datetime.datetime.strptime(t2, '%Y-%m-%d %H:%M:%S')

    if (t1 > t2 and t1 - t2 < datetime.timedelta(days=1)) or (t2 - t1 and t2 - t1 < datetime.timedelta(days=1)):
        return True
    else:
        return False

def trim_size(string):
    if len(string) > max_str_len:
        return string[:max_str_len]
    else:
        return string

""" AR field struct """
class Struct():
    _fields = []
    
    def __init__(self, *args):
        if len(args) != len(self._fields):
            raise Exception, 'expect %d args' %len(self._fields)
        for name, value in zip(self._fields, args):
            setattr(self, name, value)

class AR_Audit(Struct):
    _fields = issue_trail_fields

    def create_time_between(self, start, end):
        return time_between(self.Create_Date, start, end)

    def __str__(self):
        return 'Entry_Id=%s, Create_Date=%s' %(self.Entry_Id, str(self.Create_Date))

class AR_Trail(Struct):
    _fields = ar_trail_fields

    def __str__(self):
        return 'Request_Id=%s' %(self.Request_Id)

class AR_Note(Struct):
    _fields = ar_note_fields

    def __str__(self):
        return 'Entry_Id=%s, Full_Name=%s' %(self.Entry_Id, self.Full_Name)

class AR_Issue(Struct):
    _fields = ar_issue_fields

    def __str__(self):
        return 'Entry_Id=%s, Summary=%s' %(self.Entry_Id, self.Summary)

class AR(Struct):
    _fields = ['issue', 'audit', 'notes', 'audit_notes']

""" SQL supports """
class Sql(object):
    def __init__(self, table, fields, **kw):
        # kw include args like filters, values, ...
        if len(fields) == 0:
            raise Exception, 'SQL fields empty'
        self.table = table
        self.fields = fields
        for k in kw.keys():
            setattr(self, k, kw.pop(k))
        self._cmd = None

    def __str__(self):
        return 'SQL: table=%s fields=%s' %(self.table, self.fields)

    def _map_field_name(self, f):
        if hasattr(self, 'field_map') and self.field_map != None and f in self.field_map.keys():
            return self.field_map[f]
        return f
        
    def build_sql(self):
        raise NotImplemented('build_sql is abstract method')
    
    @property
    def cmd(self):
        if self._cmd == None:
            self.build_sql()
        return self._cmd

    @cmd.setter
    def cmd(self, v):
        raise AttributeError('can not set cmd attribute')

class Sql_Select(Sql):
    def __init__(self, table, fields, **kw):
        super(Sql_Select, self).__init__(table, fields, **kw)

    def build_sql(self):
        # 'SELECT <sth, sth> FROM <tab> WHERE (x1=y1 OR/AND x2=y2)'
        cmd = 'SELECT'
        f = self._map_field_name(self.fields[0])
        cmd += ' %s' %f
        for f in self.fields[1:]:
            f = self._map_field_name(f)
            cmd += ', %s' %f
        cmd += ' FROM %s' %(self.table)
        if hasattr(self, 'filters') and self.filters != None and len(self.filters) != 0:
            cmd += ' WHERE (%s)' %self.filters

        log('build select cmd: %s' %cmd)
        self._cmd = cmd

class Sql_Insert(Sql):
    def __init__(self, table, fields, **kw):
        super(Sql_Insert, self).__init__(table, fields, **kw)

    def build_sql(self):
        # 'INSERT INTO <tab> (sth, sth) VALUES (val, val)'
        if not hasattr(self, 'values'):
            raise AttributeError('missing values argument')
        if len(self.values) != len(self.fields):
            raise AttributeError('fields and values mismatch')

        cmd = 'INSERT INTO %s (' %self.table
        f = self._map_field_name(self.fields[0])
        cmd += '%s' %f
        for f in self.fields[1:]:
            f = self._map_field_name(f)
            cmd += ', %s' %f
        cmd += ') VALUES ('
        cmd += '\'%s\'' %self.values[0]
        for v in self.values[1:]:
            cmd += ', \'%s\'' %v
        cmd += ')'

        log('build insert cmd: %s ...' %cmd)
        self._cmd = cmd

""" database table manipulation """
class Deferred(object):
    """ 
    This class runs proc(*args) in a background thread,
    join the thread with caller method, return value of proc(*args) is returned
    """
    def __init__(self, proc, *args):
        self._proc = proc
        self._args = args
        self._done_cb = None
        self._done_cb_args = None
        self._done = False
        self._ret = None
        self._cond = threading.Condition()
        self._thread = threading.Thread(target=self._wrapper, args=(proc, args))
        self._thread.start()

    def __str__(self):
        return str(self._proc)

    def __call__(self):
        self._cond.acquire()
        while self._done == 0:
            self._cond.wait()
        self._cond.release()
        return self._ret

    def _wrapper(self, proc, args):
        self._cond.acquire()
        try:
            self._ret = proc(*args)
        except:
            # TODO: handle exception
            raise
        self._done = True
        if self._done_cb != None and self._done_cb_args != None:
            self._done_cb(*self._done_cb_args)
        self._cond.notify()
        self._cond.release()
    
    def set_done_callback(self, proc, *args):
        self._done_cb = proc
        self._done_cb_args = args

class Db_Table(object):
    def __init__(self, db, table, fields, max_workers=MAX_WORKERS):
        if len(fields) == 0:
            raise AttributeError('table fields empty')
        self.db = db
        self.db_cursor = db.cursor()
        self.table = table
        self.fields = fields
        self.max_workers = max_workers
    
    def __str__(self):
        return 'DB: table=%s, fields=%s' %(self.table, self.fields)

    def exec_insert(self, values, **kw):
        cursor = kw.get('cursor', self.db_cursor)
        if cursor == None:
            cursor = self.db_cursor
        sql = Sql_Insert(self.table, self.fields, values=values, field_map=self.db.field_map)
        cursor.execute(sql.cmd)

    def exec_select(self, filters=None, **kw):
        cursor = kw.get('cursor', self.db_cursor)
        if cursor == None:
            cursor = self.db_cursor
        if filters != None:
            sql = Sql_Select(self.table, self.fields, filters=filters, field_map=self.db.field_map)
        else:
            sql = Sql_Select(self.table, self.fields, field_map=self.db.field_map)
        cursor.execute(sql.cmd)

    def fetchone(self, **kw):
        cursor = kw.get('cursor', self.db_cursor)
        if cursor == None:
            cursor = self.db_cursor
        return cursor.fetchone()

    def fetchmany(self, size, **kw):
        cursor = kw.get('cursor', self.db_cursor)
        if cursor == None:
            cursor = self.db_cursor
        return cursor.fetchmany(size)

    def fetchall(self, **kw):
        cursor = kw.get('cursor', self.db_cursor)
        if cursor == None:
            cursor = self.db_cursor
        return cursor.fetchall()

    def run_in_parrallel(self, job_name, jobs, proc, *args):
        """
        Run proc in parrallel on the jobs iterable
        Concurrency depends on the max workers of db connection pool
        The callback is proc(tab, cursor, lock, job, *args)
        Lock is used for proc to synchronize access to their shared resources
        """
        def _done_cb(tab, conn):
            tab.db.conn_pool.put(conn)

        ds = []
        max_workers = self.db.conn_pool.max_workers
        lock = threading.Lock()
        job_cnt = len(jobs)
        for idx, j in enumerate(jobs, 1):
            log('start job(%s): %d/%d' %(job_name, idx, job_cnt))
            conn = self.db.conn_pool.get()
            cursor = conn.cursor();
            d = Deferred(proc, self, cursor, lock, j, *args)
            d.set_done_callback(_done_cb, self, conn)
            if len(ds) >= max_workers:
                ds.pop(0)
            ds.append(d)
        for d in ds:
            d()
        log('all jobs(%s) are done' %job_name)

    def fetchmany_and_proc(self, size, lock, proc, *args, **kw):
        """
        Fetch in bulk and process in bulk in single thread
        But fetchmany_and_proc can be called in multithread context
        The callback is proc(tab, cursor, lock, row, *args)
        Lock is used for proc to synchronize access to their shared resources
        """
        cursor = kw.get('cursor', None)
        fetch_more = True
        res = self.fetchmany(size, cursor=cursor)
        if len(res) == 0:
            fetch_more = False
        for row in res:
            proc(self, cursor, lock, row, *args)
        return fetch_more

    def fetchall_concurrent(self, proc, *args):
        """
        Another level of concurrency: fetch in bulk and process in bulk
        The callback is proc(tab, cursor, lock, row, *args)
        Lock is not used as the whole process is serialized
        """
        fetch_more = True
        lock = threading.Lock()
        while fetch_more:
            fetch_more = self.fetchmany_and_proc(self.max_workers, lock, proc, *args)

def AR_Audit_Tab(db):
    return Db_Table(db, issue_trail_tabname, issue_trail_fields)

def AR_Trail_Tab(db):
    return Db_Table(db, ar_trail_tabname, ar_trail_fields)

def AR_Note_Tab(db):
    return Db_Table(db, ar_note_tabname, ar_note_fields)

def AR_Issue_Tab(db):
    return Db_Table(db, ar_issue_tabname, ar_issue_fields)

""" AR Database manipulation """
class AR_Db_Connection_Pool(object):
    def __init__(self, db, max_workers=MAX_WORKERS):
        self._max_workers = max_workers
        self._db = db
        self._conn_cmd = '%s;%s' %(self._db.drv_str, self._db.conn_str)
        self._connections = []
        self._lock = threading.Lock()
        self._queue = Queue.Queue()

    def __str__(self):
        return 'AR_Db connections(%d/%d): %s' %(self._max_workers, self._queue.qsize(), self._conn_cmd)

    def _create_connection(self):
        log('connect cmd: %s' %(self._conn_cmd))
        return pyodbc.connect(self._conn_cmd, autocommit=True)

    def _destroy_connection(self):
        self._lock.acquire()
        log('destroy all connections(%d): %s' %(len(self._connections), self._conn_cmd))
        for c in self._connections:
            c.close()
        self._lock.release()

    def __del__(self):
        self._destroy_connection()

    @property
    def max_workers(self):
        return self._max_workers

    @max_workers.setter
    def max_workers(self, v):
        raise AttributeError('can not set max_workers attribute')

    def get(self):
        if len(self._connections) < self._max_workers:
            conn = self._create_connection()
            self._lock.acquire()
            self._connections.append(conn)
            self._lock.release()
            return conn
        else:
            return self._queue.get(timeout=60)

    def put(self, conn):
        if conn not in self._connections:
            raise AttributeError('put invalid connection: %s' %str(conn))
        return self._queue.put(conn)

class AR_Db(object):
    def __init__(self, name, drv_str, conn_str, field_map=None):
        """ @field_map translates from AR_Struct fields to database table fields """
        self.name = name
        self.drv_str = drv_str
        self.conn_str = conn_str
        self.field_map = field_map
        self.conn = None
        self.conn_pool = None

    def __enter__(self):
        if self.conn_pool == None:
            self.conn_pool = AR_Db_Connection_Pool(self, MAX_WORKERS)
        self.connect()
        return self

    def __exit__(self, exc_ty, exc_val, exc_tb):
        self.conn_pool = None
        self.conn = None

    def __del__(self):
        self.conn_pool = None
        self.conn = None

    def __str__(self):
        return 'AR_Db: name=%s, drv=%s, conn=%s' %(self.name, self.drv_str, self.conn_str)

    def connect(self):
        self.conn = self.conn_pool.get()

    def cursor(self):
        if self.conn == None:
            self.connect()
        return self.conn.cursor()

""" Excel manipulation """
class Excel_Sheet(object):
    def __init__(self, wb, sheet_name):
        self.wb = wb
        self.sheet_name = sheet_name
        self.index = 0
        self.ws = self.wb.add_sheet(self.sheet_name)
        self.mk_header()

    def mk_header(self):
        header = ['Entry_Id', 'Status', 'Assigned_To', 'Product_Area',
                'Prime_Bug_Id', 'Trail', 'Modified_By', 'Create_Date', 'Summary',
                'Full_Details', 'Trail_Notes', 'Notes']
        for col, val in enumerate(header):
            self.ws.write(0, col, val)
        self.index = 1

    def add_ar_line(self, ar):
        control_chars = ''.join(map(unichr, control_chars_range))
        control_char_re = re.compile('[%s]' %re.escape(control_chars))
        data = []
        data.append(str(ar.issue.Entry_Id))
        data.append(str(ar.issue.Status))
        data.append(str(ar.issue.Assigned_To))
        data.append(str(ar.issue.Product_Area))
        data.append(str(ar.issue.Prime_Bug_Id))

        from_audit = ar.audit.From_Value.split(';')
        to_audit = ar.audit.To_Value.split(';')
        if len(from_audit) != len(to_audit):
            raise Exception, 'audit not match'
        audit = []
        modified_by = []
        for f, t in zip(from_audit, to_audit):
            audit.append(f+' -> '+t+';\r\n')
            modified_by.append(t.split('|')[1]+';')
        trail_str = ''.join(audit)
        modified_by_str = ''.join(modified_by)

        data.append(control_char_re.sub('', trim_size(trail_str)))
        data.append(modified_by_str)
        data.append(str(ar.issue.Create_Date))
        data.append(str(ar.issue.Summary))
        data.append(control_char_re.sub('', trim_size(ar.issue.Full_Details)))
        data.append(control_char_re.sub('', ar.audit_notes))
        data.append(control_char_re.sub('', trim_size(ar.notes)))

        for col, val in enumerate(data):
            self.ws.write(self.index, col, val)
        self.index += 1

class Excel:
    def __init__(self, file_name):
        self.file_name = file_name
        self.wb = xlwt.Workbook()
        self.ws = {}
        if os.path.exists(file_name):
            os.remove(file_name)

    def add_sheet(self, sheet_name):
        self.ws[sheet_name] = Excel_Sheet(self.wb, sheet_name)
        return self.ws[sheet_name]

    def save(self):
        self.wb.save(self.file_name)

""" Solr manipulation """
class Solr(object):
    def __init__(self, addr, url_base, port=8983, debug=True, headers={
            'Content-type' : 'application/xml; charset=UTF-8'}):
        self.addr = addr
        self.port = port
        self.url_base = url_base
        self.headers = headers
        self.debug = debug
        self.url = '%s:%d/%s' %(self.addr, self.port, self.url_base)
        if self.debug:
            handler = urllib2.HTTPHandler(debuglevel=1)
            opener = urllib2.build_opener(handler)
            urllib2.install_opener(opener)
    def __str__(self):
        return 'url=%s' %(self.url)
    # FIXME: /?commit=true
    def _post_update(self, data):
        request = urllib2.Request(self.url+'update')
        for k, v in self.headers.iteritems():
            request.add_header(k, v)
        request.add_data(data)
        return urllib2.urlopen(request)
    def _commit_update(self):
        return self._post_update('<commit/>')
    def _optimize_update(self):
        return self._post_update('<optimize/>')
    def post_data(self, data):
        res = self._post_update(data)
        log('post data: %s' %res.read(), LOG_DETAIL)
        res = self._commit_update()
        # log('commit data: %s' %res.read())
        res = self._optimize_update()
        # log('optimize data: %s' %res.read())
    def post_file(self, file_name):
        with open(file_name, 'r') as f:
            return post_data(f.read())
    def proc_xml_special_char(self, data):
        di = dict((b, '&%s;' %a) for a, b in htmlentitydefs.entitydefs.iteritems())
        return re.sub('[<&]', lambda x: di[x.group()], data)
    def add_ar_line(self, ar):
        add = ET.Element('add')
        doc = ET.SubElement(add, 'doc')
        ar_issue_fields = ['Entry_Id', 'Assigned_To', 'Prime_Bug_Id', 'Full_Details', 
                'Root_Cause', 'Status', 'Summary']
        for k in ar_issue_fields:
            e = ET.SubElement(doc, 'field', {'name' : k})
            e.text = self.proc_xml_special_char(str(getattr(ar.issue, k)))
        e = ET.SubElement(doc, 'field', {'name' : 'Audit_Trail'})
        from_audit = ar.audit.From_Value.split(';')
        to_audit = ar.audit.To_Value.split(';')
        audit_str = ''
        for fr, to in zip(from_audit, to_audit):
            audit_str += fr + ' -> ' + to + ';\r\n'
        e.text = self.proc_xml_special_char(audit_str)
        e = ET.SubElement(doc, 'field', {'name' : 'Note_Details'})
        e.text = self.proc_xml_special_char(ar.notes)
        # log(ET.tostring(add))
        self.post_data(ET.tostring(add, encoding='UTF-8'))

def trim_dup(in_list, key):
    in_list.sort(key = lambda d: getattr(d, key))

    out_list = []
    d_len = len(in_list);
    prev = None
    for i, curr in enumerate(in_list, 1):
        # log('trim dup: %d/%d' %(i, d_len))
        if prev == None or (getattr(prev, key) != getattr(curr, key)):
            # another entry
            out_list.append(curr)
        prev = curr
    return out_list

def crawl_ar(db, start_time, end_time, export_func = None, export_db = None):
    """ export data from 'db' to 'export db' """
    ar_list = []

    # crawl 'Issue_Trail' data
    def _proc_audit(tab, cursor, lock, row, ar_list, start_time, end_time, 
            export_func, export_tab):
        log('proc audit: %s' %row)
        ar = AR_Audit(*row)
        if ar.create_time_between(start_time, end_time):
            lock.acquire()
            ar_list.append(ar)
            if export_func != None:
                export_func(export_tab, ar)
            lock.release()

    tab = AR_Audit_Tab(db)
    if export_func != None:
        export_tab = AR_Audit_Tab(export_db)
    tab.exec_select(issue_trail_filter)
    tab.fetchall_concurrent(_proc_audit, ar_list, start_time, end_time, export_func, export_tab)

    # crawl 'SHARE_Audit' data
    def _proc_trail(tab, cursor, lock, ar, export_func, export_tab):
        log('exporting trail: %s, %s' %(str(ar.Entry_Id), str(ar.Request_Id)))
        tab.exec_select('Request_Id=\'%s\'' %ar.Request_Id.split('|')[1], cursor=cursor)
        row = tab.fetchone(cursor=cursor)
        ar_trail = AR_Trail(*row)
        lock.acquire()
        if export_func != None:
            export_func(export_tab, ar_trail)
        lock.release()

    tab = AR_Trail_Tab(db)
    if export_func != None:
        export_tab = AR_Trail_Tab(export_db)
    tab.run_in_parrallel('proc Audit Trail', ar_list, _proc_trail, export_func, export_tab)

    ar_list = trim_dup(ar_list, 'Entry_Id')

    # crawl 'Issue_Notes'
    def _proc_note(tab, cursor, lock, ar, export_func, export_tab):
        log('exporting notes: %s' %str(ar.Entry_Id))
        tab.exec_select('Entry_Id=\'%s\'' %ar.Entry_Id, cursor=cursor)
        for row in tab.fetchall(cursor=cursor):
            ar_detail = AR_Note(*row)
            lock.acquire()
            if export_func != None:
                export_func(export_tab, ar_detail)
            lock.release()

    tab = AR_Note_Tab(db)
    if export_func != None:
        export_tab = AR_Note_Tab(export_db)
    tab.run_in_parrallel('proc Notes', ar_list, _proc_note, export_func, export_tab)

    # crawl 'Issue_Tracking'
    # query 'Issue_Tracking' table is slow, so fetch/process in bulk
    def _proc_issue(tab, cursor, lock, row, export_func, export_tab):
        log('exporting issue: %s' %row)
        ar_issue = AR_Issue(*row)
        lock.acquire()
        if export_func != None:
            export_func(export_tab, ar_issue)
        lock.release()

    def _proc_issue_set(tab, cursor, lock, ar_set, export_func, export_tab):
        log('exporting %d issues from %s' %(len(ar_set), str(ar_set[0].Entry_Id)))
        filters = 'Entry_Id=\'%s\'' %str(ar_set[0].Entry_Id)
        for ar in ar_set[1:]:
            filters += ' or Entry_Id=\'%s\'' %str(ar.Entry_Id)
        tab.exec_select(filters, cursor=cursor)
        tab.fetchmany_and_proc(MAX_WORKERS, lock, _proc_issue, export_func, export_tab, cursor=cursor)

    tab = AR_Issue_Tab(db)
    if export_func != None:
        export_tab = AR_Issue_Tab(export_db)
    ar_len = len(ar_list)
    ar_set_list = []
    for i in range(0, ar_len, MAX_WORKERS):
        ar_set_list.append(ar_list[i:i+MAX_WORKERS])
    tab.run_in_parrallel('proc Issue Tracking', ar_set_list, _proc_issue_set, export_func, export_tab)

def export_accdb2(tab, ar):
    # filter all control chars
    control_chars = ''.join(map(unichr, control_chars_range))
    control_char_re = re.compile('[%s]' %re.escape(control_chars))
    special_chars = '\''
    special_char_re = re.compile('[%s]' %re.escape(special_chars))
    values = []
    for f in ar._fields:
        v = str(getattr(ar, f))
        v = control_char_re.sub('', v)
        v = special_char_re.sub('"', v)
        values.append(v)
    tab.exec_insert(values)

def export_stdout(dummy, ar):
    print ar

def add_note(this_note, notes, notes_len):
    # make sure note string does not exceed max str length,
    # otherwise pop oldest notes and keep latest note
    truncated = False
    this_note_len = len(this_note)
    if this_note_len > max_str_len:
        this_note = trim_size(this_note)
        this_note_len = max_str_len
        truncated = True
    while notes_len + this_note_len > max_str_len:
        notes_len -= len(notes.pop(0))
        truncated = True
    notes.append(this_note)
    notes_len += this_note_len
    return (notes_len, truncated)

def handle_note(ar_note, notes, notes_len,
        ar_audit, audit_notes, audit_notes_len):
    notes_truncated = False
    # process note detail
    this_note = '\n>> %s by %s >>\n%s' %(str(ar_note.Note_Create_Date), 
            str(ar_note.Created_By), str(ar_note.Note_Details))
    (notes_len, notes_truncated) = add_note(this_note, notes, notes_len)
    # check if the note relates to audit trail
    for t in ar_audit.To_Value.split(';'):
        d = t.split('|')[2]
        if (ar_note.Created_By not in note_usr_filter) and same_day(ar_note.Note_Create_Date, d):
            (audit_notes_len, dummy) = add_note(this_note, 
                    audit_notes, audit_notes_len)
            break
    return (notes_len, audit_notes_len, notes_truncated)

def query_ar(db, start_time, end_time, export_func = None, export_db = None, 
        ar_audit_func = None, ar_audit_arg = None, 
        ar_issue_func = None, ar_issue_arg = None, 
        ar_note_func = None, ar_note_arg = None):
    ar_list = []
    _ar_list = []
    tab = AR_Audit_Tab(db)
    tab.exec_select(issue_trail_filter2)
    for row in tab.fetchall():
        ar = AR_Audit(*row)
        if ar.create_time_between(start_time, end_time):
            _ar_list.append(ar)

    _ar_list.sort(key = lambda ar: ar.Entry_Id)

    # get trail detail, and trim duplicated
    o_ar = None
    ar_len = len(_ar_list)
    tab = AR_Trail_Tab(db)
    for idx, ar in enumerate(_ar_list, 1): # TODO, do all ARs
        log('check tail %d/%d: %s, %s' %(idx, ar_len, ar.Entry_Id, ar.Request_Id))

        if ar_audit_func != None:
            ar_audit_func(ar, idx, ar_audit_arg)

        tab.exec_select('Request_Id=%d' %int(ar.Request_Id.split('|')[1]))
        row = tab.fetchone()
        ar_trail = AR_Trail(*row)
        ar.To_Value = str(ar.To_Value) + '|' + str(ar_trail.Last_Modified_By) + '|' + str(ar_trail.Modified_Date)
        merged = False
        if o_ar != None and o_ar.Entry_Id == ar.Entry_Id:
            # merge trail history
            ar.From_Value = str(o_ar.From_Value) + ';' + str(ar.From_Value)
            ar.To_Value = str(o_ar.To_Value) + ';' + str(ar.To_Value)
            del ar_list[-1]
            ar_list.append(ar)
            merged = True
        if merged == False:
            ar_list.append(ar)
        o_ar = ar

    # get ar notes and issue
    ar_len = len(ar_list)
    note_tab = AR_Note_Tab(db)
    issue_tab = AR_Issue_Tab(db)
    for idx, ar_audit in enumerate(ar_list, 1):
        log('query %d/%d: %s' %(idx, ar_len, ar_audit.Entry_Id))

        # query notes
        note_tab.exec_select('Entry_Id=%d' %int(ar_audit.Entry_Id))
        notes = []
        notes_len = 0
        audit_notes = []
        audit_notes_len = 0
        notes_truncated = False
        for row in note_tab.fetchall():
            ar_note = AR_Note(*row)
            if ar_note_func != None:
                ar_note_func(ar_note, idx, ar_note_arg)
            (notes_len, audit_notes_len, truncated) = handle_note(ar_note, notes, notes_len, 
                    ar_audit, audit_notes, audit_notes_len)
            if truncated:
                notes_truncated = True
        note_string = ''
        if notes_truncated:
            note_string = '!!truncated '
        note_string += ''.join(notes)
        audit_note_string = ''.join(audit_notes)

        # query ar issue
        issue_tab.exec_select('Entry_Id=%d' %int(ar_audit.Entry_Id))
        row = issue_tab.fetchone()
        ar_issue = AR_Issue(*row)

        # make statistic of the ARs
        if ar_issue_func != None:
            ar_issue_func(ar_issue, idx, ar_issue_arg)

        # export ar
        ar = AR(ar_issue, ar_audit, note_string, audit_note_string)
        if export_func != None:
            export_func(export_db, ar)

    return (len(_ar_list), len(ar_list))

def export_ar_line(target, ar):
    target.add_ar_line(ar)

class ar_audit_cb_arg(Struct):
    _fields = ['to_vdm', 'from_vdm', 'cnt']

def stat_ar_audit(ar_audit, idx, arg):
    # called before ar_audit merge duplicates
    if int(ar_audit.Entry_Id) > 668617:
        arg.cnt += 1
        if vdm_triage_str in ar_audit.To_Value:
            if ar_audit.From_Value in arg.to_vdm.keys():
                arg.to_vdm[ar_audit.From_Value] += 1
            else:
                arg.to_vdm[ar_audit.From_Value] = 1
        else:
            if ar_audit.To_Value in arg.from_vdm.keys():
                arg.from_vdm[ar_audit.To_Value] += 1
            else:
                arg.from_vdm[ar_audit.To_Value] = 1

class ar_issue_cb_arg(Struct):
    _fields = ['fixed', 'fixed_by_vdm', 'dismissed', 'dismissed_by_vdm', 'opened', 'opened_by_vdm']

def stat_ar_issue(ar_issue, idx, arg):
    if idx > 400 and ar_issue.Status == 'Fixed':
        arg.fixed += 1
    if idx > 400 and ar_issue.Status == 'Fixed' and ar_issue.Assigned_To in ar_triage_member:
        arg.fixed_by_vdm += 1
    if idx > 400 and ar_issue.Status == 'Dismissed':
        arg.dismissed += 1
    if idx > 400 and ar_issue.Status == 'Dismissed' and ar_issue.Assigned_To in ar_triage_member:
        arg.dismissed_by_vdm += 1
    if idx > 400 and ar_issue.Status == 'Open':
        arg.opened += 1
    if idx > 400 and ar_issue.Status == 'Open' and ar_issue.Assigned_To in ar_triage_member:
        arg.opened_by_vdm += 1

class ar_note_cb_arg(Struct):
    _fields = ['start_time', 'end_time', 'notes_per_person', 'ar_per_person', 'ar_history']

def stat_ar_note(ar_note, idx, arg):
    if ar_note.Created_By != 'automatos':
        log('create by %s' %ar_note.Created_By)
    if ar_note.Created_By in team_a_member and time_between(ar_note.Note_Create_Date, arg.start_time, arg.end_time):
        if ar_note.Created_By in arg.notes_per_person.keys():
            arg.notes_per_person[ar_note.Created_By] += 1
        else:
            arg.notes_per_person[ar_note.Created_By] = 1
        if not ar_note.Entry_Id in arg.ar_history.keys():
            arg.ar_history[ar_note.Entry_Id] = ar_note.Created_By
            if ar_note.Created_By in arg.ar_per_person.keys():
                arg.ar_per_person[ar_note.Created_By] += 1
            else:
                arg.ar_per_person[ar_note.Created_By] = 1

#################################################
########### Main Body of this Program ###########
#################################################

ar_crawl = False # True
export2excel = False # True
export2solr = False

try:
    opts, args = getopt.getopt(sys.argv[1:], 'ha:D:E:L:', 
            ['help', 'action=', 'local-db=', 'excel=', 'log='])
except getopt.GetoptError:
    raise
for opt, arg in opts:
    if opt in ('-h', '--help'):
        usage()
        sys.exit()
    elif opt in ('-a', '--action'):
        action = arg
        if action == 'export2excel':
            export2excel = True
        elif action == 'ar-crawl':
            ar_crawl = True
        elif action == 'export2solr':
            export2solr = True
        else:
            raise Exception, 'unknown action \"%s\"' %action
    elif opt in ('-D', '--local-db'):
        accdb_name = arg
        if not os.path.exists(accdb_name):
            raise Exception, 'accdb not found: \"%s\"' %accdb_name
    elif opt in ('-E', '--excel'):
        excel_file_name = arg
    elif opt in ('-L', '--log'):
        log_file_name = arg
        if os.path.exists(log_file_name):
            os.remove(log_file_name)
        log_file = open(log_file_name, 'w+')
    else:
        print 'unknown opt %s' %opt
        usage()
        sys.exit()

log('local_db=%s, excel=%s' %(accdb_name, excel_file_name))
log('export2excel=%d, ar_crawl=%d, export2solr=%d' %(export2excel, 
    ar_crawl, export2solr))

exec_start = datetime.datetime.now()
log('start time: %s' %exec_start)

if export2excel:
    excel = Excel(excel_file_name)

access_db = AR_Db('Microsoft Access Database', accdb_drv_string, accdb_conn_prefix+accdb_name)
log('%s' %access_db)

with access_db as accdb:

    if ar_crawl:
        # grab ARs from Remedy AR System and store in local accdb
        remedy_ar_db = AR_Db('Remedy AR System', ardb_drv_string, ardb_conn_string,
                {'Prime_Bug_Id' : 'Prime_Bug_#'})
        log('%s' %remedy_ar_db)
        with remedy_ar_db as ardb:
            crawl_ar(ardb, ar_hist_start, ar_hist_end, export_accdb2, accdb)

    if export2excel:
        log('export to excel')
        ar_audit_arg = ar_audit_cb_arg({}, {}, 0)
        ar_issue_arg = ar_issue_cb_arg(0, 0, 0, 0, 0, 0)
        # ar_note_arg = ar_note_cb_arg(datetime.datetime(2015, 5, 3, 0, 0, 0), datetime.datetime(2015, 5, 9, 0, 0, 0), {}, {}, {})
        ar_note_arg = ar_note_cb_arg(datetime.datetime(2015, 4, 26, 0, 0, 0), datetime.datetime(2015, 5, 3, 0, 0, 0), {}, {}, {})
        (ar_audit_cnt, ar_issue_cnt) = query_ar(accdb, ar_hist_start, ar_hist_end, 
                export_ar_line, excel.add_sheet('triaged_ar_list'),
                stat_ar_audit, ar_audit_arg, stat_ar_issue, ar_issue_arg,
                stat_ar_note, ar_note_arg)
        excel.save()
        log('excel file %s saved' %excel_file_name)
        print 'audit cnt: %d, issue cnt: %d, real audit cnt: %d' %(ar_audit_cnt, ar_issue_cnt, ar_audit_arg.cnt)
        print '==========================\nto vdm\n=========================='
        for k, v in ar_audit_arg.to_vdm.iteritems():
            print '%s: %d' %(k, int(v))
        print '==========================\nfrom vdm\n=========================='
        for k, v in ar_audit_arg.from_vdm.iteritems():
            print '%s: %d' %(k, int(v))
        print '=========================='
        print 'fixed: %d/%d, dismissed: %d/%d, open: %d/%d' %(ar_issue_arg.fixed, 
                ar_issue_arg.fixed_by_vdm, ar_issue_arg.dismissed, ar_issue_arg.dismissed_by_vdm,
                ar_issue_arg.opened, ar_issue_arg.opened_by_vdm)
        print '======= note per person ============='
        for k, v in ar_note_arg.notes_per_person.iteritems():
            print '%s: %d' %(k, int(v))
        print '======= ar per person ==============='
        for k, v in ar_note_arg.ar_per_person.iteritems():
            print '%s: %d' %(k, int(v))
        print '======= ar history ==============='
        for k, v in ar_note_arg.ar_history.iteritems():
            print '%s: %s' %(k, v)

    if export2solr:
        log('export to solr')
        solr = Solr('http://localhost', 'solr/ar_triage/', debug=False)
        (to_vdm, from_vdm, fixed_by_vdm, dismissed) = query_ar(accdb, 
                ar_hist_start, ar_hist_end, export_ar_line, solr)

exec_end = datetime.datetime.now()
log('end time: %s => %s, %s' %(str(exec_start), str(exec_end), str(exec_end - exec_start)))

