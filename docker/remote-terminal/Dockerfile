FROM alpine:latest
RUN sed -i 's~dl-cdn.alpinelinux.org~mirrors.aliyun.com~' /etc/apk/repositories \
        && apk --update --no-cache add bash \
        bash-doc \
        bash-completion \
        busybox-extras \
        && rm -rf /var/cache/apk/*
ADD runcmd.sh /bin
RUN chmod +x /bin/runcmd.sh
