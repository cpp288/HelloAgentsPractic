package com.trip;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;

import com.trip.config.AgentProperties;

@SpringBootApplication
@EnableConfigurationProperties(AgentProperties.class)
public class TripApiApplication {

    public static void main(String[] args) {
        SpringApplication.run(TripApiApplication.class, args);
    }

    /** 虚拟线程池：调用 Python、抓图都走它，不占用 Tomcat 线程。 */
    @Bean(destroyMethod = "close")
    public ExecutorService tripExecutor() {
        return Executors.newVirtualThreadPerTaskExecutor();
    }
}
