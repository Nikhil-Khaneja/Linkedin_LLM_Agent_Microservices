FROM eclipse-temurin:21-jre-jammy

ARG JMETER_VERSION=5.6.3
ENV JMETER_HOME=/opt/jmeter
ENV PATH=$JMETER_HOME/bin:$PATH

RUN apt-get update && apt-get install -y wget curl && rm -rf /var/lib/apt/lists/*

RUN wget -q https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-${JMETER_VERSION}.tgz \
    && tar -xzf apache-jmeter-${JMETER_VERSION}.tgz -C /opt \
    && mv /opt/apache-jmeter-${JMETER_VERSION} ${JMETER_HOME} \
    && rm apache-jmeter-${JMETER_VERSION}.tgz

WORKDIR /jmeter
COPY run_tests.sh /jmeter/run_tests.sh
RUN chmod +x /jmeter/run_tests.sh

ENTRYPOINT ["/jmeter/run_tests.sh"]
