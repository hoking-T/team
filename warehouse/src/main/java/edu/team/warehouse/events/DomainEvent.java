package edu.team.warehouse.events;
import java.util.UUID;
public record DomainEvent(String id,String type,long aggregateId,String details) {
 public static DomainEvent of(String type,long aggregateId,String details){return new DomainEvent(UUID.randomUUID().toString(),type,aggregateId,details);}
}
