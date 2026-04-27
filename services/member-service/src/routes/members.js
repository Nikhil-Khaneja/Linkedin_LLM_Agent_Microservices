const router=require('express').Router();
const {v4:uuidv4}=require('uuid');
const Joi=require('joi');
const {getDB}=require('../db/mysql');
const {getRedis}=require('../db/redis');
const {publishEvent}=require('../kafka/producer');
const {requireAuth}=require('../middleware/auth');
const {AppError}=require('../middleware/errorHandler');

const profileSchema=Joi.object({
  first_name:Joi.string().max(80).required(),
  last_name:Joi.string().max(80).required(),
  email:Joi.string().email().required(),
  phone:Joi.string().max(30).allow('',null),
  city:Joi.string().max(100).allow('',null),
  state:Joi.string().max(100).allow('',null),
  country:Joi.string().max(100).default('USA'),
  headline:Joi.string().max(220).allow('',null),
  about_summary:Joi.string().allow('',null),
  profile_photo_url:Joi.string().uri().allow('',null),
  resume_url:Joi.string().uri().allow('',null),
  resume_text:Joi.string().allow('',null),
  skills:Joi.array().items(Joi.string()).default([]),
  experience:Joi.array().items(Joi.object()).default([]),
  education:Joi.array().items(Joi.object()).default([]),
});

// POST /members/create
router.post('/create',requireAuth,async(req,res,next)=>{
  try{
    const {error,value}=profileSchema.validate(req.body);
    if(error)return next(new AppError(400,'validation_error',error.details[0].message,false));
    const db=getDB();
    const memberId='mbr_'+uuidv4().replace(/-/g,'').slice(0,16);
    await db.execute(
      'INSERT INTO members (member_id,user_id,first_name,last_name,email,phone,city,state,country,headline,about_summary,profile_photo_url,resume_url,resume_text) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
      [memberId,req.user.userId,value.first_name,value.last_name,value.email,value.phone||null,value.city||null,value.state||null,value.country,value.headline||null,value.about_summary||null,value.profile_photo_url||null,value.resume_url||null,value.resume_text||null]
    );
    // Insert skills
    for(const s of value.skills){
      await db.execute('INSERT INTO member_skills (member_id,skill_name) VALUES (?,?)',[memberId,s]);
    }
    // Insert experience
    for(const e of value.experience){
      await db.execute('INSERT INTO member_experience (member_id,company_name,title,location,start_date,end_date,is_current,description) VALUES (?,?,?,?,?,?,?,?)',
        [memberId,e.company_name,e.title,e.location||null,e.start_date||null,e.end_date||null,e.is_current?1:0,e.description||null]);
    }
    await publishEvent('member.created',{event_type:'member.created',trace_id:req.traceId,timestamp:new Date().toISOString(),actor_id:req.user.userId,entity:{entity_type:'member',entity_id:memberId},payload:{member_id:memberId},idempotency_key:uuidv4()});
    return res.status(201).json({success:true,trace_id:req.traceId,data:{member_id:memberId}});
  }catch(err){next(err);}
});

// POST /members/get
router.post('/get',requireAuth,async(req,res,next)=>{
  try{
    const {member_id}=req.body;
    // Accept member_id OR fall back to looking up by the authenticated user's id
    const lookupId = member_id || req.user.userId;
    if(!lookupId)return next(new AppError(400,'validation_error','member_id required.',false));
    const redis=getRedis();
    const cacheKey='member:'+lookupId;
    const cached=await redis.get(cacheKey);
    if(cached)return res.json({success:true,trace_id:req.traceId,data:JSON.parse(cached),meta:{cache:'hit'}});
    const db=getDB();
    // Try by member_id first, then by user_id
    let [[member]]=await db.execute('SELECT * FROM members WHERE member_id=? AND is_deleted=0',[lookupId]);
    if(!member){
      [[member]]=await db.execute('SELECT * FROM members WHERE user_id=? AND is_deleted=0',[lookupId]);
    }
    if(!member)return next(new AppError(404,'not_found','Member not found.',false));
    const [skills]=await db.execute('SELECT skill_name,proficiency FROM member_skills WHERE member_id=?',[member.member_id]);
    const [exp]=await db.execute('SELECT * FROM member_experience WHERE member_id=? ORDER BY start_date DESC',[member.member_id]);
    const [edu]=await db.execute('SELECT * FROM member_education WHERE member_id=? ORDER BY start_year DESC',[member.member_id]);
    const result={...member,skills,experience:exp,education:edu};
    await redis.set(cacheKey,JSON.stringify(result),'EX',300);
    return res.json({success:true,trace_id:req.traceId,data:result,meta:{cache:'miss'}});
  }catch(err){next(err);}
});

// POST /members/update
router.post('/update',requireAuth,async(req,res,next)=>{
  try{
    const {member_id,...updates}=req.body;
    const db=getDB();
    // Find member by member_id or user_id
    let [[member]]=await db.execute('SELECT member_id,user_id FROM members WHERE member_id=? AND is_deleted=0',[member_id||'']);
    if(!member){
      [[member]]=await db.execute('SELECT member_id,user_id FROM members WHERE user_id=? AND is_deleted=0',[req.user.userId]);
    }
    if(!member)return next(new AppError(404,'not_found','Member not found.',false));
    if(member.user_id!==req.user.userId&&req.user.userType!=='recruiter')
      return next(new AppError(403,'forbidden','Cannot update another member profile.',false));
    const allowed=['first_name','last_name','phone','city','state','country','headline','about_summary','profile_photo_url','resume_url','resume_text'];
    const fields=Object.keys(updates).filter(k=>allowed.includes(k));
    if(fields.length>0){
      const sets=fields.map(f=>f+'=?').join(',');
      await db.execute('UPDATE members SET '+sets+',version=version+1 WHERE member_id=?',[...fields.map(f=>updates[f]),member.member_id]);
    }
    const redis=getRedis();
    await redis.del('member:'+member.member_id);
    await redis.del('member:'+req.user.userId);
    return res.json({success:true,trace_id:req.traceId,data:{member_id:member.member_id,updated:fields}});
  }catch(err){next(err);}
});

// POST /members/delete
router.post('/delete',requireAuth,async(req,res,next)=>{
  try{
    const {member_id}=req.body;
    if(!member_id)return next(new AppError(400,'validation_error','member_id required.',false));
    const db=getDB();
    await db.execute('UPDATE members SET is_deleted=1 WHERE member_id=? AND user_id=?',[member_id,req.user.userId]);
    const redis=getRedis();
    await redis.del('member:'+member_id);
    return res.json({success:true,trace_id:req.traceId,data:{member_id,status:'deleted'}});
  }catch(err){next(err);}
});

// POST /members/search — powered by Elasticsearch (MySQL fallback)
router.post('/search',requireAuth,async(req,res,next)=>{
  try{
    const {skill,location,keyword,page=1,page_size=20}=req.body;
    const {searchMembers}=require('../search/memberSearch');
    const {members,source}=await searchMembers({keyword,location,skill,page,page_size});
    return res.json({
      success:true,
      trace_id:req.traceId,
      data:{members},
      meta:{page,page_size,count:members.length,search_engine:source}
    });
  }catch(err){next(err);}
});

module.exports=router;
