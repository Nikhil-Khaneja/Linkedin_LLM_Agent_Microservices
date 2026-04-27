const {Kafka}=require('kafkajs');
let producer;
async function connectKafka(clientId='service'){
  const kafka=new Kafka({
    clientId,
    brokers:(process.env.KAFKA_BROKERS||'localhost:9092').split(','),
    retry:{initialRetryTime:300,retries:10}
  });
  producer=kafka.producer();
  await producer.connect();
  console.log('['+clientId+'] Kafka producer connected');
}
async function publishEvent(topic,payload){
  if(!producer)return;
  try{
    await producer.send({topic,messages:[{key:payload.trace_id||'',value:JSON.stringify(payload)}]});
  }catch(e){console.error('[kafka] publish error:',e.message);}
}
module.exports={connectKafka,publishEvent};
