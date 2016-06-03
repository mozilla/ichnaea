FROM mysql:5.6.23
ENV MYSQL_ROOT_PASSWORD=mysql
COPY my.cnf /etc/mysql/conf.d/my.cnf
VOLUME /var/lib/mysql
EXPOSE "3306"

COPY setup.sh run.sh /
CMD ["/bin/bash", "/run.sh"]
