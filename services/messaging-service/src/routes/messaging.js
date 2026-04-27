const router=require('express').Router();
const {v4:uuidv4}=require('uuid');
const {getDB}=require('../db/mysql');
const {getMongoDB}=require('../db/mongodb');
const {getRedis}=require('../db/redis');
const {publishEvent}=require('../kafka/producer');
const {requireAuth}=require('../middleware/auth');
const {AppError}=require('../middleware/errorHandler');

// POST /threads/open
router.post('/threads/open',requireAuth,async(req,res,next)=>{
  try{
    const {participant_ids}=req.body;
    if(!participant_ids||participant_ids.length<2)return next(new AppError(400,'validation_error','At least 2 participant_ids required.',false));
    const db=getDB();
    // check existing thread
    const sorted=[...participant_ids].sort();
    const [existing]=await db.execute(
      'SELECT t.thread_id FROM threads t JOIN thread_participants tp1 ON t.thread_id=tp1.thread_id JOIN thread_participants tp2 ON t.thread_id=tp2.thread_id WHERE tp1.user_id=? AND tp2.user_id=? GROUP BY t.thread_id HAVING COUNT(DISTINCT tp1.user_id,tp2.user_id)=2',
      [sorted[0],sorted[1]]
    );
    if(existing.length>0)return res.json({success:true,trace_id:req.traceId,data:{thread_id:existing[0].thread_id,existed:true}});
    const threadId='thr_'+uuidv4().replace(/-/g,'').slice(0,16);
    await db.execute('INSERT INTO threads (thread_id) VALUES (?)',[threadId]);
    for(const uid of participant_ids){
      await db.execute('INSERT INTO thread_participants (thread_id,user_id) VALUES (?,?)',[threadId,uid]);
    }
    return res.status(201).json({success:true,trace_id:req.traceId,data:{thread_id:threadId,existed:false}});
  }catch(err){next(err);}
});

// POST /threads/get
router.post('/threads/get',requireAuth,async(req,res,next)=>{
  try{
    const {thread_id}=req.body;
    if(!thread_id)return next(new AppError(400,'validation_error','thread_id required.',false));
    const db=getDB();
    const [[thread]]=await db.execute('SELECT * FROM threads WHERE thread_id=?',[thread_id]);
    if(!thread)return next(new AppError(404,'not_found','Thread not found.',false));
    const [participants]=await db.execute('SELECT user_id,unread_count FROM thread_participants WHERE thread_id=?',[thread_id]);
    return res.json({success:true,trace_id:req.traceId,data:{...thread,participants}});
  }catch(err){next(err);}
});

// POST /threads/byUser
router.post('/threads/byUser',requireAuth,async(req,res,next)=>{
  try{
    const {user_id}=req.body;
    if(!user_id)return next(new AppError(400,'validation_error','user_id required.',false));
    const db=getDB();
    const [rows]=await db.execute(
      'SELECT t.thread_id,t.last_message_at,tp.unread_count FROM threads t JOIN thread_participants tp ON t.thread_id=tp.thread_id WHERE tp.user_id=? ORDER BY t.last_message_at DESC LIMIT 50',
      [user_id]
    );
    return res.json({success:true,trace_id:req.traceId,data:{threads:rows}});
  }catch(err){next(err);}
});

// POST /messages/list
router.post('/messages/list',requireAuth,async(req,res,next)=>{
  try{
    const {thread_id,cursor,page_size=50}=req.body;
    if(!thread_id)return next(new AppError(400,'validation_error','thread_id required.',false));
    const mongo=getMongoDB();
    const query={thread_id,is_deleted:{$ne:true}};
    if(cursor)query['_id']={$lt:require('mongodb').ObjectId(cursor)};
    const messages=await mongo.collection('messages').find(query).sort({sent_at:-1}).limit(page_size).toArray();
    return res.json({success:true,trace_id:req.traceId,data:{messages:messages.reverse()},meta:{count:messages.length,has_more:messages.length===page_size}});
  }catch(err){next(err);}
});

// POST /messages/send
// Rate limit: 60 messages per minute per user
router.post('/messages/send',requireAuth,async(req,res,next)=>{
  try{
    try {
      const redis = getRedis();
      if (redis) {
        const key = `rate:message:${req.user.userId}`;
        const count = await redis.incr(key);
        if (count === 1) await redis.expire(key, 60);
        if (count > 60) {
          const ttl = await redis.ttl(key);
          return res.status(429).json({ success:false, trace_id:req.traceId, error:{ code:'rate_limited', message:`Too many messages. Wait ${ttl}s.`, retryable:true }});
        }
      }
    } catch(e) {}
    const {thread_id,content}=req.body;
    if(!thread_id||!content)return next(new AppError(400,'validation_error','thread_id and content required.',false));
    const idempKey=req.headers['idempotency-key']||uuidv4();
    const mongo=getMongoDB();
    const existing=await mongo.collection('messages').findOne({idempotency_key:idempKey});
    if(existing)return res.json({success:true,trace_id:req.traceId,data:{message_id:existing._id.toString(),idempotent:true}});
    const msgDoc={thread_id,sender_id:req.user.userId,content,sent_at:new Date(),trace_id:req.traceId,idempotency_key:idempKey,is_deleted:false};
    const result=await mongo.collection('messages').insertOne(msgDoc);
    const db=getDB();
    await db.execute('UPDATE threads SET last_message_at=NOW() WHERE thread_id=?',[thread_id]);
    await db.execute('UPDATE thread_participants SET unread_count=unread_count+1 WHERE thread_id=? AND user_id!=?',[thread_id,req.user.userId]);
    await publishEvent('message.sent',{event_type:'message.sent',trace_id:req.traceId,timestamp:new Date().toISOString(),actor_id:req.user.userId,entity:{entity_type:'thread',entity_id:thread_id},payload:{thread_id,message_id:result.insertedId.toString()},idempotency_key:idempKey});
    return res.status(201).json({success:true,trace_id:req.traceId,data:{message_id:result.insertedId.toString()}});
  }catch(err){next(err);}
});

// POST /connections/request
router.post('/connections/request',requireAuth,async(req,res,next)=>{
  try{
    const {receiver_id,message}=req.body;
    if(!receiver_id)return next(new AppError(400,'validation_error','receiver_id required.',false));
    const db=getDB();
    const [existing]=await db.execute('SELECT request_id FROM connection_requests WHERE requester_id=? AND receiver_id=?',[req.user.userId,receiver_id]);
    if(existing.length>0)return next(new AppError(409,'duplicate_request','Connection request already sent.',false));
    const reqId='creq_'+uuidv4().replace(/-/g,'').slice(0,16);
    await db.execute('INSERT INTO connection_requests (request_id,requester_id,receiver_id,message) VALUES (?,?,?,?)',[reqId,req.user.userId,receiver_id,message||null]);
    await publishEvent('connection.requested',{event_type:'connection.requested',trace_id:req.traceId,timestamp:new Date().toISOString(),actor_id:req.user.userId,entity:{entity_type:'connection',entity_id:reqId},payload:{request_id:reqId,receiver_id},idempotency_key:uuidv4()});
    return res.status(201).json({success:true,trace_id:req.traceId,data:{request_id:reqId}});
  }catch(err){next(err);}
});

// POST /connections/accept
router.post('/connections/accept',requireAuth,async(req,res,next)=>{
  try{
    const {request_id}=req.body;
    if(!request_id)return next(new AppError(400,'validation_error','request_id required.',false));
    const db=getDB();
    const [[req_row]]=await db.execute('SELECT * FROM connection_requests WHERE request_id=?',[request_id]);
    if(!req_row)return next(new AppError(404,'not_found','Request not found.',false));
    if(req_row.receiver_id!==req.user.userId)return next(new AppError(403,'forbidden','Not your request.',false));
    await db.execute('UPDATE connection_requests SET status=? WHERE request_id=?',['accepted',request_id]);
    const [u1,u2]=[req_row.requester_id,req_row.receiver_id].sort();
    await db.execute('INSERT IGNORE INTO connections (user_id_1,user_id_2) VALUES (?,?)',[u1,u2]);
    await publishEvent('connection.accepted',{event_type:'connection.accepted',trace_id:req.traceId,timestamp:new Date().toISOString(),actor_id:req.user.userId,entity:{entity_type:'connection',entity_id:request_id},payload:{request_id,accepted_by:req.user.userId},idempotency_key:uuidv4()});
    return res.json({success:true,trace_id:req.traceId,data:{request_id,status:'accepted'}});
  }catch(err){next(err);}
});

// POST /connections/reject
router.post('/connections/reject',requireAuth,async(req,res,next)=>{
  try{
    const {request_id}=req.body;
    if(!request_id)return next(new AppError(400,'validation_error','request_id required.',false));
    const db=getDB();
    await db.execute('UPDATE connection_requests SET status=\'rejected\' WHERE request_id=? AND receiver_id=?',[request_id,req.user.userId]);
    return res.json({success:true,trace_id:req.traceId,data:{request_id,status:'rejected'}});
  }catch(err){next(err);}
});

// POST /connections/list
router.post('/connections/list',requireAuth,async(req,res,next)=>{
  try{
    const {user_id}=req.body;
    if(!user_id)return next(new AppError(400,'validation_error','user_id required.',false));
    const db=getDB();
    const [rows]=await db.execute(
      'SELECT c.*,u.first_name,u.last_name FROM connections c JOIN users u ON (CASE WHEN c.user_id_1=? THEN c.user_id_2 ELSE c.user_id_1 END)=u.user_id WHERE c.user_id_1=? OR c.user_id_2=?',
      [user_id,user_id,user_id]
    );
    return res.json({success:true,trace_id:req.traceId,data:{connections:rows}});
  }catch(err){next(err);}
});

// POST /connections/mutual
router.post('/connections/mutual',requireAuth,async(req,res,next)=>{
  try{
    const {user_id,other_id}=req.body;
    if(!user_id||!other_id)return next(new AppError(400,'validation_error','user_id and other_id required.',false));
    const db=getDB();
    const [rows]=await db.execute(
      'SELECT u.user_id,u.first_name,u.last_name FROM connections c1 JOIN connections c2 ON (CASE WHEN c1.user_id_1=? THEN c1.user_id_2 ELSE c1.user_id_1 END)=(CASE WHEN c2.user_id_1=? THEN c2.user_id_2 ELSE c2.user_id_1 END) JOIN users u ON u.user_id=(CASE WHEN c1.user_id_1=? THEN c1.user_id_2 ELSE c1.user_id_1 END) WHERE (c1.user_id_1=? OR c1.user_id_2=?) AND (c2.user_id_1=? OR c2.user_id_2=?)',
      [user_id,other_id,user_id,user_id,user_id,other_id,other_id]
    );
    return res.json({success:true,trace_id:req.traceId,data:{mutual_connections:rows,count:rows.length}});
  }catch(err){next(err);}
});

module.exports=router;
