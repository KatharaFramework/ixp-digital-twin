FROM kathara/base

ARG DEBIAN_FRONTEND="noninteractive"
RUN apt update
RUN apt install -y openntpd \
    snmp

RUN apt install -y ntp

RUN apt clean && \
    rm -rf /tmp/* /var/lib/apt/lists/* /var/tmp/*