package edu.team.warehouse.api;
import jakarta.validation.constraints.*;
public final class Requests {
 private Requests(){}
 public record Product(@NotBlank @Pattern(regexp="[A-Za-z0-9_-]{1,40}") String code,@NotBlank @Size(max=100) String name,@NotBlank @Size(max=20) String unit){}
 public record Movement(@NotNull @Positive Long productId,@NotNull @Positive Long locationId,@NotNull @Min(1) @Max(1000000) Long quantity){}
 public record Advance(@NotBlank @Pattern(regexp="TRANSIT|DELIVERED") String status){}
}
