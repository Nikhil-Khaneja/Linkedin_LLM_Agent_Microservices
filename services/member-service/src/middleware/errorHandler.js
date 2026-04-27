class AppError extends Error{
  constructor(status,code,message,retryable=false,details=null){
    super(message);this.status=status;this.code=code;this.retryable=retryable;this.details=details;
  }
}
function errorHandler(err,req,res,next){
  const traceId=req.traceId||'unknown';
  if(err instanceof AppError)
    return res.status(err.status).json({success:false,trace_id:traceId,error:{code:err.code,message:err.message,details:err.details,retryable:err.retryable}});
  console.error('[error]',err);
  return res.status(500).json({success:false,trace_id:traceId,error:{code:'internal_error',message:'An unexpected error occurred.',retryable:true}});
}
module.exports={AppError,errorHandler};
