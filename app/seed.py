import json
from app.db import DataSource, MetadataTable, MetadataColumn, Domain, Subject, Task, ValidationResult, SystemSetting
from app.services import DEFAULT_SQL
from app.workspace import WorkspaceManager


def seed(db):
    if db.query(DataSource).count()==0:
        ds1=DataSource(name='StarRocks 生产数仓',type='STARROCKS',host='prod-starrocks',port=9030,username='readonly',environment='PROD',readonly=True)
        ds2=DataSource(name='Agent Dev StarRocks',type='STARROCKS',host='agent-dev-starrocks',port=9030,username='agent',environment='DEV',readonly=False)
        ds3=DataSource(name='业务 MySQL',type='MYSQL',host='business-mysql',port=3306,username='readonly',environment='PROD',readonly=True)
        db.add_all([ds1,ds2,ds3]); db.commit(); db.refresh(ds1)
        specs=[('dwd','dwd_trade_order_detail','DWD','交易域','订单主题',128392114),('dwd','dwd_trade_payment_detail','DWD','交易域','支付主题',102381824),('dwd','dwd_trade_refund_detail','DWD','交易域','退款主题',6822011),('dws','dws_trade_city_day','DWS','交易域','订单主题',3281992),('ads','ads_trade_dashboard','ADS','交易域','经营分析',1261009)]
        for dbn,name,layer,domain,subject,rows in specs:
            mt=MetadataTable(datasource_id=ds1.id,database_name=dbn,table_name=name,layer=layer,domain=domain,subject=subject,row_count=rows,table_comment=name,ddl=f'CREATE TABLE {dbn}.{name} (...);'); db.add(mt); db.flush()
            if name=='dwd_trade_order_detail':
                cols=[('order_id','BIGINT','订单唯一标识','主键'),('user_id','BIGINT','用户标识','维度'),('city_code','VARCHAR(20)','城市编码','维度'),('channel_code','VARCHAR(30)','订单渠道','维度'),('pay_amount','DECIMAL(18,2)','实际支付金额','指标候选'),('dt','DATE','业务日期','分区')]
                for i,(n,t,c,r) in enumerate(cols,1): db.add(MetadataColumn(table_id=mt.id,name=n,data_type=t,comment=c,ordinal=i,nullable=n not in {'order_id','dt'},role=r))
    if db.query(Domain).count()==0:
        definitions=[('trade','交易域',82,['订单主题','支付主题','退款主题']),('user','用户域',46,['用户主题','会员主题']),('product','商品域',51,['商品主题','类目主题','品牌主题']),('marketing','营销域',39,['活动主题','优惠券主题']),('supply','供应链域',67,['库存主题','采购主题']),('common','公共域',42,['地区主题','日期主题'])]
        for code,name,cnt,subs in definitions:
            d=Domain(code=code,name=name,table_count=cnt); db.add(d); db.flush()
            for i,s in enumerate(subs,1): db.add(Subject(domain_id=d.id,code=f'{code}_{i}',name=s))
    if db.query(Task).count()==0:
        design={'domain':'交易域','subject':'订单主题','layer':'DWS','model_name':'dws_trade_city_channel_day','grain':['dt','city_code','channel_code'],'metrics':['order_count','pay_user_count','pay_amount','refund_amount'],'source_context':[]}
        t=Task(task_no='DW-20260911-001',title='城市渠道订单日汇总',requirement='按城市、渠道统计支付金额、支付用户数、退款金额',domain='交易域',subject='订单主题',model_name='dws_trade_city_channel_day',phase='HUMAN_REVIEW',status='WAITING_HUMAN_REVIEW',design_json=json.dumps(design,ensure_ascii=False),sql_code=DEFAULT_SQL,owner='Yang'); db.add(t); db.commit(); db.refresh(t)
        t.workspace_path=str(WorkspaceManager().create_task_workspace(t.task_no,t.requirement,design,DEFAULT_SQL,t.model_name))
        vals=[('SQL 执行成功','SUCCESS','SUCCESS',0.0),('主键唯一性','0','0',0.0),('关键字段 NULL','0','0',0.0),('支付金额对账','18,520,341.23','18,520,341.23',0.0),('订单数对账','1,823,019','1,823,019',0.0),('退款金额对账','1,219,388.70','1,219,388.70',0.0),('数据波动检查','±20%','+3.6%',3.6)]
        for n,e,a,d in vals: db.add(ValidationResult(task_id=t.id,rule_name=n,expected_value=e,actual_value=a,difference_rate=d,status='PASS'))
    if db.query(SystemSetting).count()==0:
        for k,v in {'agent.mode':'auto_until_human_review','source.mode':'dolphinscheduler_mysql_to_local','source.readonly':'true','production.write':'false','release.auto_publish_ds':'false'}.items(): db.add(SystemSetting(key=k,value=v))
    db.commit()
