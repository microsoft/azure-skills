# Spring Dependency Configuration Patterns

Common dependency and configuration patterns to identify during assessment.

## Database Configuration

**Maven (pom.xml):**
```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-data-jpa</artifactId>
</dependency>
```

**application.properties:**
```properties
spring.datasource.url=jdbc:mysql://localhost:3306/mydb
spring.datasource.username=dbuser
spring.datasource.driver-class-name=com.mysql.cj.jdbc.Driver
```

**application.yml:**
```yaml
spring:
  data:
    mongodb:
      uri: mongodb://<username>:<password>@server:27017
```

## JMS Message Brokers

**ActiveMQ (pom.xml):**
```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-activemq</artifactId>
</dependency>
```

**application.properties:**
```properties
spring.activemq.broker-url=tcp://localhost:61616
spring.activemq.user=admin
```

## External Caches

**Redis with Spring Data Redis:**
- Check for `spring-boot-starter-data-redis` dependency
- Review application.properties for Redis connection strings
- Check for Spring Session configuration (in-memory → Redis)
